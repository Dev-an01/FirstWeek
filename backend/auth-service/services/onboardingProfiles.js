const { findProjectMembership } = require('./projectAccess');
const { cleared } = require('./projectConversations');

const profileOf = member => ({ onboardingRole: member.onboardingRole ?? null,
  onboardingExperience: member.onboardingExperience ?? null, profileVersion: member.profileVersion ?? 0 });
function fail(status, message) { throw Object.assign(new Error(message), { status }); }
async function readProfile(prisma, actor, projectId) {
  const member = await findProjectMembership(prisma, actor, projectId);
  if (!member) fail(404, 'Project resource not found.');
  return profileOf(member);
}
async function saveProfile(prisma, actor, projectId, body) {
  if (!body || typeof body !== 'object' || Array.isArray(body) || Object.keys(body).length !== 2 ||
      ![null, 'ENGINEERING', 'PRODUCT', 'DESIGN', 'OPERATIONS'].includes(body.onboardingRole) ||
      ![null, 'NEW', 'EXPERIENCED'].includes(body.onboardingExperience)) {
    fail(400, 'Choose an onboarding focus and experience, or null to clear each preference.');
  }
  return prisma.$transaction(async tx => {
    await tx.$queryRaw`SELECT id FROM projects WHERE "companyId" = ${actor.companyId} AND id = ${projectId} FOR UPDATE`;
    const current = await readProfile(tx, actor, projectId);
    if (current.onboardingRole === body.onboardingRole && current.onboardingExperience === body.onboardingExperience) return current;
    const scope = { companyId: actor.companyId, projectId, userId: actor.id };
    const member = await tx.projectMember.update({ where: { companyId_projectId_userId: scope },
      data: { onboardingRole: body.onboardingRole, onboardingExperience: body.onboardingExperience, profileVersion: { increment: 1 } } });
    await tx.projectConversation.updateMany({ where: scope, data: { ...cleared,
      title: 'Conversation reset after onboarding changes', knowledgeHash: '', version: { increment: 1 } } });
    return profileOf(member);
  });
}
module.exports = { profileOf, readProfile, saveProfile };
