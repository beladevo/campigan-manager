import { Module } from "@nestjs/common";
import { TypeOrmModule } from "@nestjs/typeorm";
import { ConfigModule, ConfigService } from "@nestjs/config";
import { ClientsModule, Transport } from "@nestjs/microservices";
import * as Joi from "joi";
import { CampaignModule } from "./campaign/campaign.module";
import { Campaign } from "./campaign/entities/campaign.entity";

@Module({
  imports: [
    ConfigModule.forRoot({
      isGlobal: true,
      validationSchema: Joi.object({
        POSTGRES_HOST: Joi.string().default('postgres'),
        POSTGRES_PORT: Joi.number().default(5432),
        POSTGRES_USER: Joi.string().default('postgres'),
        POSTGRES_PASSWORD: Joi.string().default('postgres'),
        POSTGRES_DATABASE: Joi.string().default('solara'),
        RABBITMQ_URL: Joi.string().default('amqp://rabbitmq:rabbitmq@rabbitmq:5672'),
        RABBITMQ_PREFETCH_COUNT: Joi.number().default(100),
        RABBITMQ_EXCHANGE: Joi.string().default('solara.campaigns'),
      }),
    }),
    TypeOrmModule.forRootAsync({
      inject: [ConfigService],
      useFactory: (configService: ConfigService) => ({
        type: "postgres",
        host: configService.get('POSTGRES_HOST'),
        port: configService.get('POSTGRES_PORT'),
        username: configService.get('POSTGRES_USER'),
        password: configService.get('POSTGRES_PASSWORD'),
        database: configService.get('POSTGRES_DATABASE'),
        entities: [Campaign],
        synchronize: true,
      }),
    }),
    ClientsModule.registerAsync([
      {
        name: 'CAMPAIGN_SERVICE',
        inject: [ConfigService],
        useFactory: (configService: ConfigService) => ({
          transport: Transport.RMQ,
          options: {
            urls: [configService.get('RABBITMQ_URL')],
            queue: 'campaign.result',
            noAck: false,
            prefetchCount: configService.get('RABBITMQ_PREFETCH_COUNT'),
            queueOptions: {
              durable: true,
              arguments: {
                'x-dead-letter-exchange': 'solara.campaigns.dlx',
                'x-dead-letter-routing-key': 'campaign.result.failed',
              },
            },
            socketOptions: {
              heartbeatIntervalInSeconds: 60,
              reconnectTimeInSeconds: 5,
            },
          },
        }),
      },
    ]),
    CampaignModule,
  ],
})
export class AppModule {}