import * as dotenv from 'dotenv';
import { NestFactory } from '@nestjs/core';
import { Transport, MicroserviceOptions } from '@nestjs/microservices';
import { ValidationPipe, Logger } from '@nestjs/common';
import { AppModule } from './app.module';

dotenv.config();

async function bootstrap() {
  const logger = new Logger('Bootstrap');
  
  try {
    // Create hybrid application (HTTP + Microservice)
    const app = await NestFactory.create(AppModule);
    
    // Enable global validation
    app.useGlobalPipes(new ValidationPipe({
      transform: true,
      whitelist: true,
      forbidNonWhitelisted: true,
    }));
    
    // Connect microservice for RabbitMQ message consumption
    const rabbitmqUrl = process.env.RABBITMQ_URL || 'amqp://rabbitmq:rabbitmq@localhost:5672';
    logger.log(`Attempting to connect to RabbitMQ at: ${rabbitmqUrl.replace(/:[^:@]*@/, ':***@')}`);
    
    app.connectMicroservice<MicroserviceOptions>({
      transport: Transport.RMQ,
      options: {
        urls: [rabbitmqUrl],
        queue: 'campaign.result',
        queueOptions: {
          durable: true,
        },
        socketOptions: {
          heartbeatIntervalInSeconds: 60,
          reconnectTimeInSeconds: 5,
        },
      },
    });

    // Start both HTTP server and microservice
    await app.startAllMicroservices();
    await app.listen(3000);
    
    logger.log('NestJS service listening on port 3000');
    logger.log('RabbitMQ microservice connected for campaign.result queue');
    logger.log(`Environment: ${process.env.NODE_ENV || 'development'}`);
    logger.log(`RabbitMQ URL: ${rabbitmqUrl.replace(/:[^:@]*@/, ':***@')}`);
    
  } catch (error) {
    logger.error('Failed to start application:', error);
    process.exit(1);
  }
}

bootstrap();
