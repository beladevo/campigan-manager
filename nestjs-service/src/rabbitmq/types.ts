import { IsString, IsNotEmpty, IsOptional, IsUUID } from 'class-validator';

export class CampaignGenerationMessage {
  @IsUUID()
  @IsNotEmpty()
  campaignId: string;

  @IsString()
  @IsNotEmpty()
  prompt: string;
}

export class CampaignResultMessage {
  @IsUUID()
  @IsNotEmpty()
  campaignId: string;

  @IsString()
  generatedText: string;

  @IsString()
  imagePath: string;

  @IsOptional()
  @IsString()
  error?: string;
}