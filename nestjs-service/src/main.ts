import * as dotenv from "dotenv";
import { NestFactory } from "@nestjs/core";
import { Transport, MicroserviceOptions } from "@nestjs/microservices";
import { ValidationPipe, Logger } from "@nestjs/common";
import { AppModule } from "./app.module";
import { ConfigService } from "./config/config.service";

dotenv.config();

async function bootstrap() {
  const logger = new Logger("Bootstrap");

  try {
    const app = await NestFactory.create(AppModule);

    const configService = app.get(ConfigService);

    app.useGlobalPipes(
      new ValidationPipe({
        transform: true,
        whitelist: true,
        forbidNonWhitelisted: true,
      })
    );

    logger.log(
      `Attempting to connect to RabbitMQ at: ${configService.rabbitmqUrlForLogging}`
    );

    app.connectMicroservice<MicroserviceOptions>({
      transport: Transport.RMQ,
      options: {
        urls: [configService.rabbitmqUrl],
        queue: "campaign.result",
        queueOptions: {
          durable: true,
        },
        socketOptions: {
          heartbeatIntervalInSeconds: 60,
          reconnectTimeInSeconds: 5,
        },
      },
    });

    await app.startAllMicroservices();
    await app.listen(configService.port);

    logger.log(`NestJS service listening on port ${configService.port}`);
    logger.log("RabbitMQ microservice connected for campaign.result queue");
    logger.log(`Environment: ${configService.nodeEnv}`);
    logger.log(`RabbitMQ URL: ${configService.rabbitmqUrlForLogging}`);
  } catch (error) {
    logger.error("Failed to start application:", error);
    process.exit(1);
  }
}

bootstrap();
