import { Injectable, Logger, NotFoundException, Controller } from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { Repository } from 'typeorm';
import { EventPattern, Ctx, RmqContext } from '@nestjs/microservices';
import { Campaign, CampaignStatus } from './entities/campaign.entity';
import { CreateCampaignDto } from './dto/create-campaign.dto';
import { RabbitMQService } from '../rabbitmq/rabbitmq.service';
import { CampaignResultMessage } from '../rabbitmq/types';

@Controller()
@Injectable()
export class CampaignService {
  private readonly logger = new Logger(CampaignService.name);
  
  constructor(
    @InjectRepository(Campaign)
    private campaignRepository: Repository<Campaign>,
    private rabbitMQService: RabbitMQService,
  ) {}
  
  async create(createCampaignDto: CreateCampaignDto): Promise<Campaign> {
    const campaign = this.campaignRepository.create({
      ...createCampaignDto,
      status: CampaignStatus.PENDING,
    });

    const savedCampaign = await this.campaignRepository.save(campaign);
    this.logger.log(`Campaign created with ID: ${savedCampaign.id}`);

    // Publish to queue
    try {
      await this.rabbitMQService.publishCampaignGeneration({
        campaignId: savedCampaign.id,
        prompt: savedCampaign.prompt,
      });
      
      // Update status to indicate it's been queued
      await this.updateCampaignStatus(savedCampaign.id, CampaignStatus.PROCESSING);
      this.logger.log(`Campaign ${savedCampaign.id} queued for processing`);
    } catch (error) {
      this.logger.error(`Failed to queue campaign ${savedCampaign.id}:`, error);
      await this.updateCampaignStatus(
        savedCampaign.id, 
        CampaignStatus.FAILED, 
        `Failed to queue: ${error.message}`
      );
    }

    return savedCampaign;
  }

  async findOne(id: string): Promise<Campaign> {
    const campaign = await this.campaignRepository.findOne({ where: { id } });
    
    if (!campaign) {
      this.logger.warn('Campaign not found', { campaignId: id });
      throw new NotFoundException(`Campaign with ID ${id} not found`);
    }
    
    this.logger.log('Campaign retrieved', {
      campaignId: id,
      status: campaign.status,
    });
    
    return campaign;
  }

  @EventPattern('campaign.result')
  async handleCampaignResult(
    message: any,
    @Ctx() context: RmqContext,
  ): Promise<void> {
    const channel = context.getChannelRef();
    const originalMsg = context.getMessage();
    const startTime = Date.now();
    
    let campaignData: CampaignResultMessage | null = null;
    
    try {
      this.logger.log('Received campaign result message', {
        messageId: originalMsg.properties?.messageId,
        timestamp: new Date().toISOString(),
      });
      
      // Handle different message formats
      if (message.data) {
        // NestJS microservice format: {pattern: "campaign.result", data: {...}}
        campaignData = message.data;
      } else if (message.campaignId) {
        // Direct format
        campaignData = message;
      } else {
        this.logger.error('Invalid message format received', {
          message: JSON.stringify(message),
          messageId: originalMsg.properties?.messageId,
        });
        // Reject message without requeue for invalid format
        channel.nack(originalMsg, false, false);
        return;
      }
      
      const { campaignId, generatedText, imagePath, error } = campaignData;
      
      this.logger.log('Processing campaign result', {
        campaignId,
        hasError: !!error,
        hasGeneratedText: !!generatedText,
        hasImagePath: !!imagePath,
      });
      
      if (error) {
        this.logger.error('Campaign generation failed', {
          campaignId,
          error,
        });
        await this.updateCampaignStatus(campaignId, CampaignStatus.FAILED, error);
      } else {
        this.logger.log('Campaign generation completed successfully', {
          campaignId,
          textLength: generatedText?.length || 0,
          imagePath,
        });
        
        await this.campaignRepository.update(campaignId, {
          status: CampaignStatus.COMPLETED,
          generatedText,
          imagePath,
          errorMessage: null,
        });
      }
      
      // Acknowledge successful processing
      channel.ack(originalMsg);
      
      const duration = Date.now() - startTime;
      this.logger.log('Campaign result processed successfully', {
        campaignId,
        duration,
      });
      
    } catch (dbError) {
      const duration = Date.now() - startTime;
      const campaignId = campaignData?.campaignId || 'unknown';
      
      this.logger.error('Failed to process campaign result', {
        campaignId,
        error: dbError.message,
        stack: dbError.stack,
        duration,
        messageId: originalMsg.properties?.messageId,
      });
      
      // Decide whether to requeue based on error type
      const shouldRequeue = this.shouldRequeueMessage(dbError, originalMsg);
      
      if (shouldRequeue) {
        this.logger.warn('Requeuing message for retry', {
          campaignId,
          messageId: originalMsg.properties?.messageId,
        });
        channel.nack(originalMsg, false, true);
      } else {
        this.logger.error('Rejecting message - sending to dead letter queue', {
          campaignId,
          messageId: originalMsg.properties?.messageId,
        });
        channel.nack(originalMsg, false, false);
        
        // Update campaign status to failed if we can identify it
        if (campaignData?.campaignId) {
          try {
            await this.updateCampaignStatus(
              campaignData.campaignId,
              CampaignStatus.FAILED,
              `Database error: ${dbError.message}`
            );
          } catch (updateError) {
            this.logger.error('Failed to update campaign status after rejection', {
              campaignId: campaignData.campaignId,
              error: updateError.message,
            });
          }
        }
      }
    }
  }

  private shouldRequeueMessage(error: any, message: any): boolean {
    // Get retry count from message headers
    const retryCount = message.properties?.headers?.['x-retry-count'] || 0;
    const maxRetries = 3;
    
    // Don't requeue if max retries exceeded
    if (retryCount >= maxRetries) {
      return false;
    }
    
    // Requeue for transient errors (connection issues, timeouts)
    if (error.code === 'ECONNREFUSED' || 
        error.code === 'ETIMEDOUT' || 
        error.message?.includes('connection')) {
      return true;
    }
    
    // Don't requeue for validation or constraint errors
    if (error.code === '23505' || // unique violation
        error.code === '23503' || // foreign key violation
        error.message?.includes('validation')) {
      return false;
    }
    
    // Default: requeue once for unknown errors
    return retryCount === 0;
  }

  private async updateCampaignStatus(
    campaignId: string, 
    status: CampaignStatus, 
    errorMessage?: string
  ): Promise<void> {
    await this.campaignRepository.update(campaignId, {
      status,
      errorMessage,
    });
  }
}
