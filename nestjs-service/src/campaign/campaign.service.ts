import { Injectable, Logger, NotFoundException } from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { Repository } from 'typeorm';
import axios from 'axios';
import { Campaign, CampaignStatus } from './entities/campaign.entity';
import { CreateCampaignDto } from './dto/create-campaign.dto';

@Injectable()
export class CampaignService {
  private readonly logger = new Logger(CampaignService.name);
  private readonly pythonServiceUrl = process.env.PYTHON_SERVICE_URL || 'http://python-generator:8000';
  
  constructor(
    @InjectRepository(Campaign)
    private campaignRepository: Repository<Campaign>,
  ) {}
  
  async create(createCampaignDto: CreateCampaignDto): Promise<Campaign> {
    const campaign = this.campaignRepository.create({
      ...createCampaignDto,
      status: CampaignStatus.PENDING,
    });
    console.log("🚀 ~ CampaignService ~ pythonServiceUrl:", this.pythonServiceUrl)

    const savedCampaign = await this.campaignRepository.save(campaign);
    this.logger.log(`Campaign created with ID: ${savedCampaign.id}`);

    this.processWithRetry(savedCampaign.id).catch(error => {
      this.logger.error(`Failed to process campaign ${savedCampaign.id}:`, error);
    });

    return savedCampaign;
  }

  async findOne(id: string): Promise<Campaign> {
    const campaign = await this.campaignRepository.findOne({ where: { id } });
    if (!campaign) {
      throw new NotFoundException(`Campaign with ID ${id} not found`);
    }
    return campaign;
  }

  private async processWithRetry(campaignId: string, maxRetries = 3): Promise<void> {
    let attempt = 0;
    
    while (attempt < maxRetries) {
      try {
        await this.processCampaign(campaignId);
        return;
      } catch (error) {
        attempt++;
        this.logger.warn(`Attempt ${attempt} failed for campaign ${campaignId}:`, error.message);
        
        if (attempt >= maxRetries) {
          await this.updateCampaignStatus(
            campaignId, 
            CampaignStatus.FAILED, 
            `Failed after ${maxRetries} attempts: ${error.message}`
          );
          throw error;
        }
        
        const delay = Math.pow(2, attempt) * 1000;
        await new Promise(resolve => setTimeout(resolve, delay));
      }
    }
  }

  private async processCampaign(campaignId: string): Promise<void> {
    this.logger.log(`Processing campaign ${campaignId}`);
    
    await this.updateCampaignStatus(campaignId, CampaignStatus.PROCESSING);

    const campaign = await this.findOne(campaignId);
    
    try {
      const response = await axios.post(`${this.pythonServiceUrl}/generate`, {
        campaignId: campaign.id,
        prompt: campaign.prompt,
      }, {
        timeout: 300000,
      });

      const { generatedText, imagePath } = response.data;
      
      await this.campaignRepository.update(campaignId, {
        status: CampaignStatus.COMPLETED,
        generatedText,
        imagePath,
        errorMessage: null,
      });

      this.logger.log(`Campaign ${campaignId} completed successfully`);
    } catch (error) {
      this.logger.error(`Campaign ${campaignId} processing failed:`, error);
      throw error;
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
