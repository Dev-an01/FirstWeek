// This predicate is shared by every FirstWeek read, including post-generation checks.
function projectScope(user, projectId) {
  if (!user?.id || !user.companyId || !user.isActive || !user.isCompanyVerified) {
    return null;
  }
  if (typeof projectId !== 'string' || !/^[a-z0-9][a-z0-9-]{0,79}$/.test(projectId)) {
    return null;
  }
  return {
    companyId: user.companyId,
    projectId,
    userId: user.id,
    project: { isActive: true },
    user: { isActive: true, isCompanyVerified: true },
  };
}

async function findProjectMembership(prisma, user, projectId) {
  const where = projectScope(user, projectId);
  return where ? prisma.projectMember.findFirst({ where, include: { project: true } }) : null;
}

module.exports = { projectScope, findProjectMembership };
