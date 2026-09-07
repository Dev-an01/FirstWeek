const axios = require("axios");
const { createLogger } = require("../shared/utils/logger");

const logger = createLogger("onboarding-service");

const ONBOARDING_SERVICE_URL = process.env.ONBOARDING_SERVICE_URL || "http://onboarding-service:8002";

/**
 * Service to interact with the Onboarding Service API
 */
const onboardingService = {
    /**
     * Sync a newly created company to the Onboarding Service
     * @param {Object} company - The company object from Auth DB
     */
    async syncCreateCompany(company) {
        try {
            logger.info("Syncing company to Onboarding Service", {
                companyId: company.id,
                name: company.name,
            });

            // Onboarding Service expects: { id, name, industry, description, metadata }
            const payload = {
                id: company.id,
                name: company.name,
                // Default values as Auth DB doesn't have these yet
                industry: "Technology",
                description: "",
                metadata: {
                    source: "auth-service-sync",
                    allowedDomains: company.allowedDomains || [],
                },
            };

            await axios.post(`${ONBOARDING_SERVICE_URL}/api/v1/companies`, payload);

            logger.info("Successfully synced company to Onboarding Service", {
                companyId: company.id,
            });
        } catch (error) {
            // Soft failure - log but don't throw
            logger.error("Failed to sync company to Onboarding Service", {
                companyId: company.id,
                error: error.message,
                response: error.response?.data,
            });
        }
    },

    /**
     * Sync a new executive to the Onboarding Service
     * @param {Object} user - The user object from Auth DB
     * @param {String} companyId - The company ID
     */
    async syncCreateExecutive(user, companyId) {
        try {
            const fullName = `${user.firstName} ${user.lastName}`;

            // Check if an executive with this email already exists (e.g. manually created persona)
            try {
                const searchResponse = await axios.get(
                    `${ONBOARDING_SERVICE_URL}/api/v1/companies/${companyId}/executives`,
                    { params: { email: user.email } }
                );
                const executives = searchResponse.data?.executives || [];
                if (Array.isArray(executives) && executives.length > 0) {
                    const existing = executives[0];
                    logger.info("Executive already exists for this email, updating instead of creating", {
                        existingId: existing.id,
                        email: user.email,
                        companyId,
                    });
                    // Update the existing record — but only fields that won't overwrite
                    // persona data (skip name if the executive already has a profile)
                    const patchData = { title: user.title || "Executive" };
                    if (!existing.has_profile) {
                        patchData.name = fullName;
                    }
                    await axios.patch(
                        `${ONBOARDING_SERVICE_URL}/api/v1/companies/${companyId}/executives/${existing.id}`,
                        patchData
                    );
                    return { success: true, executiveId: existing.id };
                }
            } catch (lookupError) {
                logger.warn("Email lookup failed during create, proceeding with create", {
                    email: user.email,
                    error: lookupError.message,
                });
            }

            // No existing executive found — create a new one
            const cleanName = fullName.toLowerCase().replace(/[^a-z0-9]/g, '_').replace(/_+/g, '_').replace(/^_|_$/g, '');
            const shortId = user.id.slice(-4).toLowerCase();
            const executiveId = `${cleanName}_${shortId}`;

            logger.info("Syncing executive to Onboarding Service", {
                userId: user.id,
                executiveId,
                companyId,
            });

            const payload = {
                id: executiveId,
                name: fullName,
                company_id: companyId,
                email: user.email,
                title: user.title || "Executive",
                hierarchy_level: 1,
            };

            await axios.post(`${ONBOARDING_SERVICE_URL}/api/v1/companies/${companyId}/executives`, payload);

            logger.info("Successfully synced executive to Onboarding Service", {
                executiveId,
                companyId,
            });

            return { success: true, executiveId };
        } catch (error) {
            // Soft failure - log but don't throw (or rethrow if critical?)
            // For now, we log error so the main transaction doesn't fail, 
            // but arguably we might want to alert the admin.
            logger.error("Failed to sync executive to Onboarding Service", {
                userId: user.id,
                companyId,
                error: error.message,
                response: error.response?.data,
            });
            return { success: false, error: error.message };
        }
    },

    /**
     * Sync an updated executive to the Onboarding Service
     * Looks up by email (stable identifier), then PATCHes if found or falls back to create.
     * @param {Object} user - The user object from Auth DB
     * @param {String} companyId - The company ID
     */
    async syncUpdateExecutive(user, companyId) {
        try {
            const fullName = `${user.firstName} ${user.lastName}`;

            logger.info("Syncing executive update to Onboarding Service", {
                userId: user.id,
                email: user.email,
                companyId,
            });

            // Step 1: Lookup executive by email
            let existingExecutive = null;
            try {
                const searchResponse = await axios.get(
                    `${ONBOARDING_SERVICE_URL}/api/v1/companies/${companyId}/executives`,
                    { params: { email: user.email } }
                );
                const executives = searchResponse.data?.executives || [];
                if (Array.isArray(executives) && executives.length > 0) {
                    existingExecutive = executives[0];
                }
            } catch (lookupError) {
                logger.warn("Executive lookup failed, will attempt create fallback", {
                    userId: user.id,
                    email: user.email,
                    error: lookupError.message,
                });
            }

            // Step 2: If found, PATCH the existing record
            if (existingExecutive) {
                const executiveId = existingExecutive.id;
                const payload = {
                    name: fullName,
                    title: user.title || "Executive",
                };

                await axios.patch(
                    `${ONBOARDING_SERVICE_URL}/api/v1/companies/${companyId}/executives/${executiveId}`,
                    payload
                );

                logger.info("Successfully updated executive in Onboarding Service", {
                    executiveId,
                    companyId,
                });

                return { success: true, executiveId };
            }

            // Step 3: Not found — fall back to create
            logger.info("Executive not found in Onboarding Service, falling back to create", {
                userId: user.id,
                companyId,
            });
            return await this.syncCreateExecutive(user, companyId);
        } catch (error) {
            logger.error("Failed to sync executive update to Onboarding Service", {
                userId: user.id,
                companyId,
                error: error.message,
                response: error.response?.data,
            });
            return { success: false, error: error.message };
        }
    },

    /**
     * Sync ALL executives and their companies to the Onboarding Service.
     * Called on auth-service startup to reconcile any drift (e.g. after restart/redeploy).
     * Retries with backoff if the onboarding service isn't ready yet.
     */
    async syncAllExecutives(retries = 5, delayMs = 5000) {
        for (let attempt = 1; attempt <= retries; attempt++) {
            try {
                const { prisma } = require("../shared/lib/databaseUtils");

                // 1. Sync all companies
                const companies = await prisma.company.findMany({ where: { isActive: true } });
                for (const company of companies) {
                    await this.syncCreateCompany(company);
                }
                logger.info(`Startup sync: synced ${companies.length} companies`);

                // 2. Sync all EXECUTIVE users — ensure each has an executive profile matched by email
                const executives = await prisma.user.findMany({
                    where: { role: "EXECUTIVE", isActive: true, companyId: { not: null } },
                });

                let synced = 0;
                for (const exec of executives) {
                    const result = await this.syncCreateExecutive(exec, exec.companyId);
                    if (result?.success) synced++;
                }

                logger.info(`Startup sync: synced ${synced}/${executives.length} executives`);
                return { companies: companies.length, executives: synced };
            } catch (error) {
                logger.error(`Startup executive sync attempt ${attempt}/${retries} failed`, {
                    error: error.message,
                });
                if (attempt < retries) {
                    const wait = delayMs * attempt;
                    logger.info(`Retrying executive sync in ${wait / 1000}s...`);
                    await new Promise((r) => setTimeout(r, wait));
                } else {
                    logger.error("Startup executive sync exhausted all retries");
                    return { companies: 0, executives: 0, error: error.message };
                }
            }
        }
    },
};

module.exports = onboardingService;
