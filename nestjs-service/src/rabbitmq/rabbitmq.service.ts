import { Injectable, OnApplicationShutdown, Logger } from "@nestjs/common";
import {
  ClientProxy,
  ClientProxyFactory,
  Transport,
} from "@nestjs/microservices";
import { ConfigService } from "@nestjs/config";
import { CampaignGenerationMessage, CampaignResultMessage } from "./types";

@Injectable()
export class RabbitMQService implements OnApplicationShutdown {
  private readonly logger = new Logger(RabbitMQService.name);
  private client: ClientProxy;

  constructor(private readonly configService: ConfigService) {
    this.client = ClientProxyFactory.create({
      transport: Transport.RMQ,
      options: {
        urls: [this.configService.rabbitmqUrl],
        queue: "campaign.generate", // Queue for publishing messages
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
    this.client.connect().catch((error) => {
      this.logger.error(`Failed to connect RabbitMQ client: ${error}`);
    });

    this.logger.log(
      `RabbitMQ client initialized for URL: ${this.configService.rabbitmqUrlForLogging}`
    );
    this.logger.log(`Publishing to queue: campaign.generate`);
  }

  async onApplicationShutdown() {
    try {
      await this.client.close();
      this.logger.log("RabbitMQ client connection closed");
    } catch (error) {
      this.logger.error("Error closing RabbitMQ client connection:", error);
    }
  }

  async publishCampaignGeneration(
    message: CampaignGenerationMessage
  ): Promise<void> {
    try {
      this.logger.log(
        `Publishing campaign generation message: ${JSON.stringify(message)}`
      );

      // Ensure client is connected
      if (!this.client) {
        throw new Error("RabbitMQ client not initialized");
      }

      // Connect if not already connected
      await this.client.connect();

      const result = await this.client
        .emit("campaign.generate", message)
        .toPromise();
      this.logger.log(
        `Successfully published campaign generation message for campaign: ${message.campaignId}`
      );
      this.logger.log(`Publish result: ${JSON.stringify(result)}`);
    } catch (error) {
      this.logger.error(
        `Failed to publish campaign generation message: ${error}`
      );
      this.logger.error(`Error stack: ${error.stack}`);
      throw error;
    }
  }

  async setupDeadLetterExchange(): Promise<void> {
    try {
      // This would typically be done during application startup
      // or as part of infrastructure setup
      this.logger.log('Dead letter exchange setup would be handled by infrastructure');
    } catch (error) {
      this.logger.error('Failed to setup dead letter exchange', {
        error: error.message,
        stack: error.stack,
      });
    }
  }
}
