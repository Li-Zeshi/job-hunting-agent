# Led cross-team monolith-to-microservice migration

**Situation:** Our legacy monolith was reaching its limits — deployments took 4 hours, scaling was impossible, and a single bug could bring down the entire system.

**Task:** I was responsible for architecting and leading the migration to a microservice architecture, coordinating across 3 teams in 2 time zones.

**Action:**
- Designed the service boundaries using domain-driven design
- Created a phased migration plan: strangler fig pattern
- Set up shared CI/CD pipelines, monitoring, and documentation
- Led weekly sync meetings across Amsterdam and Berlin offices
- Built a feature flag system for gradual rollout

**Result:** Migration completed 2 weeks ahead of schedule. Zero downtime during cutover. Deployment time reduced from 4 hours to 15 minutes. System reliability improved from 99.5% to 99.99%.
