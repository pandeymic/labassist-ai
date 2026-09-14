import 'reflect-metadata';
import { NestFactory } from '@nestjs/core';
import { ExpressAdapter } from '@nestjs/platform-express';
import app from './app';
import { AppModule } from './nest.module';

async function bootstrap() {
  const nest = await NestFactory.create(AppModule, new ExpressAdapter(app), { logger: ['error', 'warn', 'log'] });
  const port = Number(process.env.API_PORT || 4000);
  await nest.listen(port);
  console.log(`NestJS Provider Ops API listening on ${port}`);
}

bootstrap();
