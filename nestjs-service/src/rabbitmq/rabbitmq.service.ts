import { Injectable, OnApplicationShutdown, Logger } from '@nestjs/common';
import {
  ClientProxy,
  ClientProxyFactory,
  Transport,
} from '@nestjs/microservices';
import { CampaignGenerationMessage, CampaignResultMessage } from './types'; 

@Injectable()
export class RabbitMQService implements OnApplicationShutdown {
  private readonly logger = new Logger(RabbitMQService.name);
  private client: ClientProxy;

  constructor() {
    const rabbitmqUrl = process.env.RABBITMQ_URL || 'amqp://rabbitmq:rabbitmq@localhost:5672';
    
    this.client = ClientProxyFactory.create({
      transport: Transport.RMQ,
      options: {
        urls: [rabbitmqUrl],
        queue: 'campaign.generate', // Queue for publishing messages
        queueOptions: {
          durable: true,
        },
        socketOptions: {
          heartbeatIntervalInSeconds: 60,
          reconnectTimeInSeconds: 5,
        },
      },
    });
    
    // Connect the client immediately to detect connection issues
    this.client.connect().catch(error => {
      this.logger.error(`Failed to connect RabbitMQ client: ${error}`);
    });
    
    this.logger.log(`RabbitMQ client initialized for URL: ${rabbitmqUrl.replace(/:[^:@]*@/, ':***@')}`);
    this.logger.log(`Publishing to queue: campaign.generate`);
  }

  async onApplicationShutdown() {
    try {
      await this.client.close();
      this.logger.log('RabbitMQ client connection closed');
    } catch (error) {
      this.logger.error('Error closing RabbitMQ client connection:', error);
    }
  }

  async publishCampaignGeneration(message: CampaignGenerationMessage): Promise<void> {
    try {
      this.logger.log(`Publishing campaign generation message: ${JSON.stringify(message)}`);
      
      // Ensure client is connected
      if (!this.client) {
        throw new Error('RabbitMQ client not initialized');
      }
      
      // Connect if not already connected
      await this.client.connect();
      
      const result = await this.client.emit('campaign.generate', message).toPromise();
      this.logger.log(`Successfully published campaign generation message for campaign: ${message.campaignId}`);
      this.logger.log(`Publish result: ${JSON.stringify(result)}`);
    } catch (error) {
      this.logger.error(`Failed to publish campaign generation message: ${error}`);
      this.logger.error(`Error stack: ${error.stack}`);
      throw error;
    }
  }

  async publishCampaignResult(message: CampaignResultMessage): Promise<void> {
    try {
      await this.client.emit('campaign.result', message).toPromise();
      this.logger.log(`Published campaign result message for campaign: ${message.campaignId}`);
    } catch (error) {
      this.logger.error(`Failed to publish campaign result message: ${error}`);
      throw error;
    }
  }
}
