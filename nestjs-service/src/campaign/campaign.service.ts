import {
  Injectable,
  Logger,
  NotFoundException,
  Controller,
} from "@nestjs/common";
import { InjectRepository } from "@nestjs/typeorm";
import { Repository } from "typeorm";
import { EventPattern } from "@nestjs/microservices";
import { Campaign, CampaignStatus } from "./entities/campaign.entity";
import { CreateCampaignDto } from "./dto/create-campaign.dto";
import { RabbitMQService } from "../rabbitmq/rabbitmq.service";
import { CampaignResultMessage } from "../rabbitmq/types";

@Controller()
@Injectable()
export class CampaignService {
  private readonly logger = new Logger(CampaignService.name);

  constructor(
    @InjectRepository(Campaign)
    private campaignRepository: Repository<Campaign>,
    private rabbitMQService: RabbitMQService
  ) {}

  async create(createCampaignDto: CreateCampaignDto): Promise<Campaign> {
    const campaign = this.campaignRepository.create({
      ...createCampaignDto,
      status: CampaignStatus.PENDING,
    });

    const savedCampaign = await this.campaignRepository.save(campaign);
    this.logger.log(`Campaign created with ID: ${savedCampaign.id}`);

    try {
      await this.rabbitMQService.publishCampaignGeneration({
        campaignId: savedCampaign.id,
        prompt: savedCampaign.prompt,
      });

      await this.updateCampaignStatus(
        savedCampaign.id,
        CampaignStatus.PROCESSING
      );
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
      throw new NotFoundException(`Campaign with ID ${id} not found`);
    }
    return campaign;
  }

  @EventPattern("campaign.result")
  async handleCampaignResult(message: any): Promise<void> {
    this.logger.log(
      `Received campaign result message: ${JSON.stringify(message)}`
    );

    let campaignData: CampaignResultMessage;

    try {
      // Handle different message formats
      if (message.data) {
        // NestJS microservice format: {pattern: "campaign.result", data: {...}}
        campaignData = message.data;
      } else if (message.campaignId) {
        // Direct format
        campaignData = message;
      } else {
        this.logger.error(
          `Invalid message format received: ${JSON.stringify(message)}`
        );
        return;
      }

      const { campaignId, generatedText, imagePath, error } = campaignData;
      this.logger.log(`Processing campaign result for ID: ${campaignId}`);

      if (error) {
        this.logger.error(`Campaign ${campaignId} failed: ${error}`);
        await this.updateCampaignStatus(
          campaignId,
          CampaignStatus.FAILED,
          error
        );
      } else {
        this.logger.log(`Campaign ${campaignId} completed successfully`);
        this.logger.log(`Generated text length: ${generatedText?.length || 0}`);
        this.logger.log(`Image path: ${imagePath}`);

        await this.campaignRepository.update(campaignId, {
          status: CampaignStatus.COMPLETED,
          generatedText,
          imagePath,
          errorMessage: null,
        });

        this.logger.log(
          `Database updated successfully for campaign ${campaignId}`
        );
      }
    } catch (dbError) {
      this.logger.error(
        `Failed to update campaign ${
          campaignData?.campaignId || "unknown"
        } in database:`,
        dbError
      );
      this.logger.error(`Database error stack: ${dbError.stack}`);
      // Could potentially publish to a dead letter queue here
    }
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
