import { Body, Controller, Get, Param, Post, Logger } from '@nestjs/common';
import { CampaignService } from './campaign.service';
import { CreateCampaignDto } from './dto/create-campaign.dto';
import { Campaign } from './entities/campaign.entity';

@Controller('campaigns')
export class CampaignController {
  private readonly logger = new Logger(CampaignController.name);

  constructor(private readonly campaignService: CampaignService) {}

  @Post()
  async createCampaign(@Body() createCampaignDto: CreateCampaignDto): Promise<Campaign> {
    this.logger.log(`Creating campaign for user: ${createCampaignDto.userId}`);
    return this.campaignService.create(createCampaignDto);
  }

  @Get(':id')
  async getCampaign(@Param('id') id: string): Promise<Campaign> {
    this.logger.log(`Fetching campaign with ID: ${id}`);
    return this.campaignService.findOne(id);
  }
}
