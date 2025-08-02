import { Logger } from '@nestjs/common';

export interface RetryOptions {
  maxRetries?: number;
  initialDelayMs?: number;
  maxDelayMs?: number;
  backoffMultiplier?: number;
  jitterFactor?: number;
  shouldRetry?: (error: any, attempt: number) => boolean;
}

export class ExponentialBackoff {
  private readonly logger = new Logger(ExponentialBackoff.name);

  constructor(private readonly options: RetryOptions = {}) {
    this.options = {
      maxRetries: 3,
      initialDelayMs: 1000,
      maxDelayMs: 30000,
      backoffMultiplier: 2,
      jitterFactor: 0.1,
      shouldRetry: (error: any) => true,
      ...options,
    };
  }

  async execute<T>(
    operation: () => Promise<T>,
    operationName: string = 'operation'
  ): Promise<T> {
    let lastError: any;

    for (let attempt = 0; attempt <= this.options.maxRetries!; attempt++) {
      try {
        if (attempt > 0) {
          this.logger.log(
            `Retrying ${operationName} (attempt ${attempt + 1}/${
              this.options.maxRetries! + 1
            })`
          );
        }

        return await operation();
      } catch (error) {
        lastError = error;

        if (attempt === this.options.maxRetries) {
          this.logger.error(
            `${operationName} failed after ${this.options.maxRetries + 1} attempts: ${error}`
          );
          throw error;
        }

        if (!this.options.shouldRetry!(error, attempt)) {
          this.logger.warn(
            `${operationName} failed and should not retry: ${error}`
          );
          throw error;
        }

        const delay = this.calculateDelay(attempt);
        this.logger.warn(
          `${operationName} failed (attempt ${attempt + 1}), retrying in ${delay}ms: ${error}`
        );

        await this.sleep(delay);
      }
    }

    throw lastError;
  }

  private calculateDelay(attempt: number): number {
    const baseDelay = this.options.initialDelayMs! * Math.pow(this.options.backoffMultiplier!, attempt);
    const jitter = baseDelay * this.options.jitterFactor! * Math.random();
    const delayWithJitter = baseDelay + jitter;
    
    return Math.min(delayWithJitter, this.options.maxDelayMs!);
  }

  private sleep(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }
}

export function withExponentialBackoff<T>(
  operation: () => Promise<T>,
  options?: RetryOptions,
  operationName?: string
): Promise<T> {
  const backoff = new ExponentialBackoff(options);
  return backoff.execute(operation, operationName);
}