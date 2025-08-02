import { Module } from "@nestjs/common";
import { TypeOrmModule } from "@nestjs/typeorm";
import { CampaignModule } from "./campaign/campaign.module";
import { Campaign } from "./campaign/entities/campaign.entity";
import { ConfigModule } from "./config/config.module";
import { ConfigService } from "./config/config.service";
import { ClientsModule, Transport } from "@nestjs/microservices";

@Module({
  imports: [
    ConfigModule,
    TypeOrmModule.forRootAsync({
      imports: [ConfigModule],
      useFactory: (configService: ConfigService) => ({
        type: "postgres",
        host: configService.postgresHost,
        port: configService.postgresPort,
        username: configService.postgresUser,
        password: configService.postgresPassword,
        database: configService.postgresDatabase,
        entities: [Campaign],
        synchronize: true,
      }),
      inject: [ConfigService],
    }),
    CampaignModule,
  ],
})
export class AppModule {}