# Mini Solara System PRO-Live

Welcome to Solara AI's senior backend engineering challenge. Your task is to build a small two-service system that generates real text and images from a prompt. The project uses **NestJS** for the API layer and **Python** for the AI workload. Only minimal scaffolding is provided – you must implement all business logic yourself.

## Overview
1. A user sends `POST /campaigns` with a text prompt.
2. The NestJS service stores a job in PostgreSQL and forwards the prompt to the Python service.
3. The Python service calls **Google Gemini** for text and uses **Stable Diffusion** to create an image.
4. Results are returned to NestJS which updates the database.
5. The user polls `GET /campaigns/:id` to retrieve status and outputs.

## Provided Boilerplate
- Minimal NestJS application in `nestjs-service/`
- Minimal Python service in `python-generator/`
- `docker-compose.yml` for running both services with PostgreSQL
- Example environment file `.env.example`
- Placeholder scripts under `scripts/`

## Assignment Tasks
- Implement REST endpoints in NestJS to create a campaign and fetch its status.
- Persist job data in PostgreSQL (`campaigns` table suggested in the PRD).
- Connect to the Python service via HTTP and handle failures with retries and logging.
- In the Python service, integrate Google Gemini and Stable Diffusion to produce real output. Save images to the `output/` folder.
- Include structured logs containing the job ID throughout the workflow.
- Ensure `docker-compose up --build` starts the stack successfully.

Bonus ideas: exponential backoff logic, metrics endpoint, or notes on how you would deploy this to Kubernetes.

## Setup Instructions
1. Copy the environment template and fill in your Gemini API key:
   ```bash
   cp .env.example .env
   ```
2. Start the services:
   ```bash
   docker-compose up --build
   ```

The NestJS API will be available on `http://localhost:3000`.

## API Endpoints
### `POST /campaigns`
Enqueue a new campaign generation request.
Example body:
```json
{
  "userId": "u123",
  "prompt": "Create a beach scene with a cat"
}
```

### `GET /campaigns/:id`
Fetch the current status and generated results for a campaign.

## Submission
Share your completed project as a GitHub repository or zipped archive. Feel free to include a short write-up describing any design decisions or trade-offs.
