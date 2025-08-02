import { Injectable, OnApplicationShutdown, Logger } from "@nestjs/common";
import {
  ClientProxy,
  ClientProxyFactory,
  Transport,
} from "@nestjs/microservices";
import { CampaignGenerationMessage, CampaignResultMessage } from "./types";
import { ConfigService } from "../config/config.service";
import { withExponentialBackoff } from "../utils/exponential-backoff";

@Injectable()
export class RabbitMQService implements OnApplicationShutdown {
  private readonly logger = new Logger(RabbitMQService.name);
  private client: ClientProxy;

  constructor(private readonly configService: ConfigService) {
    this.client = ClientProxyFactory.create({
      transport: Transport.RMQ,
      options: {
        urls: [this.configService.rabbitmqUrl],
        queue: "campaign.generate",
        queueOptions: {
          durable: true,
        },
        socketOptions: {
          heartbeatIntervalInSeconds: 60,
          reconnectTimeInSeconds: 5,
        },
      },
    });

    withExponentialBackoff(
      () => this.client.connect(),
      {
        maxRetries: 5,
        initialDelayMs: 2000,
        shouldRetry: (error: any) => {
          return !error.message?.includes('ACCESS_REFUSED');
        }
      },
      'RabbitMQ client connection'
    ).catch((error) => {
      this.logger.error(`Failed to connect RabbitMQ client after retries: ${error}`);
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
    this.logger.log(
      `Publishing campaign generation message: ${JSON.stringify(message)}`
    );

    return withExponentialBackoff(
      async () => {
        if (!this.client) {
          throw new Error("RabbitMQ client not initialized");
        }

        await this.client.connect();

        const result = await this.client
          .emit("campaign.generate", message)
          .toPromise();
        
        this.logger.log(
          `Successfully published campaign generation message for campaign: ${message.campaignId}`
        );
        this.logger.log(`Publish result: ${JSON.stringify(result)}`);
        
        return result;
      },
      {
        maxRetries: 3,
        initialDelayMs: 1000,
        shouldRetry: (error: any) => {
          return !error.message?.includes('validation');
        }
      },
      `Publishing campaign message ${message.campaignId}`
    );
  }
}
