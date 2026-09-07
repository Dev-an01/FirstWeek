"""Deployment: writes profiles to PostgreSQL, Neo4j, and triggers embedding generation."""

from .neo4j_deployer import Neo4jDeployer, get_neo4j_deployer

__all__ = ["Neo4jDeployer", "get_neo4j_deployer"]
