# Week 1 : Project Setup and Understanding

## Objective

The objective of Week 1 was to establish the backend and database development environment for CivicSight and verify that the basic backend infrastructure is working correctly.

## Work Completed

### 1. Set Up the FastAPI Project

Created the initial FastAPI backend structure for CivicSight.

The backend will act as the main interface between the frontend, database and future road-damage detection component.

### 2. Configured Uvicorn

Configured Uvicorn as the development server for running the FastAPI application locally.

The backend was tested to ensure that the application can start successfully.

### 3. Set Up PostgreSQL

Installed and configured PostgreSQL locally as the relational database for CivicSight.

The database will eventually store information related to users, road-damage reports, locations, detections, priorities and repair status.

### 4. Configured SQLAlchemy

Set up SQLAlchemy as the database interaction layer.

This provides the foundation for defining database models and interacting with PostgreSQL through the backend.

### 5. Created Environment Configuration

Created an `.env` configuration approach for storing environment-specific values such as database connection details.

Sensitive configuration values are not intended to be hard-coded into the application.

### 6. Implemented Basic API Endpoints

Implemented the initial:

- `/`
- `/health`

endpoints.

These endpoints were used to verify that the backend is running correctly.

### 7. Tested Database Connectivity

Tested the connection between the FastAPI backend and PostgreSQL.

This establishes the foundation for creating the actual CivicSight database schema in the following weeks.

## Challenges / Observations

One of the main considerations was keeping configuration separate from application code.

The database layer was also kept modular so that the initial setup can later be extended with multiple entities and relationships without restructuring the entire backend.

## Learning

This week helped me understand the initial architecture of a FastAPI application and how the backend communicates with a relational database.

I also gained practical experience with environment configuration, database connectivity and API health checking.

## Week 1 Outcome

The FastAPI backend, Uvicorn server and PostgreSQL environment have been set up. SQLAlchemy and environment configuration have also been prepared, providing the foundation for the backend and database development of CivicSight.