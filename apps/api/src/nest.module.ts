import { Module } from '@nestjs/common';

/**
 * NestJS composition root for the demo API. The route implementation remains
 * Express-compatible so Supertest and the local fallback store stay simple;
 * Nest owns the HTTP lifecycle and is the extension point for future modules.
 */
@Module({ imports: [] })
export class AppModule {}
