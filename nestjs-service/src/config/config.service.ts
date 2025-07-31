import { Injectable, Logger } from "@nestjs/common";

@Injectable()
export class ConfigService {
  private readonly logger = new Logger(ConfigService.name);

  constructor() {
    this.validateEnvironment();
  }

  private validateEnvironment(): void {
    const requiredVars = ["RABBITMQ_URL"];
    const missingVars: string[] = [];

    for (const varName of requiredVars) {
      const value = process.env[varName];
      if (!value || value.trim() === "") {
        missingVars.push(varName);
      }
    }

    if (missingVars.length > 0) {
      const error = `Missing required environment variables: ${missingVars.join(
        ", "
      )}`;
      this.logger.error(error);
      throw new Error(error);
    }

    this.logger.log("Environment variables validation successful");
  }

  get postgresHost(): string {
    return process.env.POSTGRES_HOST || "localhost";
  }

  get postgresPort(): number {
    return parseInt(process.env.POSTGRES_PORT) || 5432;
  }

  get postgresUser(): string {
    return process.env.POSTGRES_USER || "postgres";
  }

  get postgresPassword(): string {
    return process.env.POSTGRES_PASSWORD || "postgres";
  }

  get postgresDatabase(): string {
    return process.env.POSTGRES_DB || "solara";
  }

  get rabbitmqUrl(): string {
    return (
      process.env.RABBITMQ_URL || "amqp://rabbitmq:rabbitmq@localhost:5672"
    );
  }

  get nodeEnv(): string {
    return process.env.NODE_ENV || "development";
  }

  get port(): number {
    return parseInt(process.env.PORT) || 3000;
  }

  get logLevel(): string {
    return process.env.LOG_LEVEL || "info";
  }

  /**
   * Get sanitized RabbitMQ URL for logging (hides password)
   */
  get rabbitmqUrlForLogging(): string {
    return this.rabbitmqUrl.replace(/:[^:@]*@/, ":***@");
  }
}
