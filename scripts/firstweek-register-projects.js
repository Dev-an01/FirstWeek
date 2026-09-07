// Run only after the additive membership migration, with explicit real identities.
const fs = require('node:fs');
const path = require('node:path');
const { prisma } = require('../backend/auth-service/shared/lib/prisma');
const args = process.argv.slice(2);
const option = (name) => args[args.indexOf(name) + 1];
async function main() {
  if (!args.includes('--company') || !args.includes('--member')) {
    throw new Error('Usage: node scripts/firstweek-register-projects.js --company COMPANY_ID --member USER_ID');
  }
  const companyId = option('--company');
  const userId = option('--member');
  const member = await prisma.user.findFirst({ where: { id: userId, companyId, isActive: true, isCompanyVerified: true } });
  if (!member) throw new Error('An active, verified member of this company is required');
  const manifest = JSON.parse(fs.readFileSync(path.join(__dirname, '../knowledge/firstweek/manifest.json'), 'utf8'));
  await prisma.$transaction(async (tx) => {
    await tx.project.updateMany({ where: { companyId, id: { in: manifest.retiredProjectIds || [] } }, data: { isActive: false } });
    for (const project of manifest.projects) {
      await tx.project.upsert({
        where: { companyId_id: { companyId, id: project.id } },
        create: { companyId, id: project.id, name: project.name, description: project.summary },
        update: { name: project.name, description: project.summary, isActive: true },
      });
      await tx.projectMember.upsert({
        where: { companyId_projectId_userId: { companyId, projectId: project.id, userId } },
        create: { companyId, projectId: project.id, userId, role: 'MAINTAINER' },
        update: {},
      });
    }
  });
  console.log(`Registered ${manifest.projects.length} projects for the explicitly selected member. Rebuild the index with the same --company ID.`);
}
main().catch(() => { console.error('Project registration failed. Check the schema, company and member IDs.'); process.exitCode = 1; })
  .finally(() => prisma.$disconnect());
