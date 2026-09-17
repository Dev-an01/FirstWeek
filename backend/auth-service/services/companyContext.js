const { createHash } = require('node:crypto');
const { listTeams } = require('./companyTeams');
function excerpt(value) {
  let result = '', bytes = 0;
  for (const character of value) {
    bytes += Buffer.byteLength(character);
    if (bytes > 4000) return `${result}\n[Excerpt truncated.]`;
    result += character;
  }
  return result;
}

async function companyContext(prisma, actor) {
  const { teams } = await listTeams(prisma, actor);
  return { teams, hash: teams.length ? createHash('sha256').update(JSON.stringify(teams)).digest('hex') : '' };
}
function companySources(context, question) {
  const words = [...new Set((question.toLowerCase().match(/[\p{L}\p{N}]{3,}/gu) || []))];
  const rows = context.teams.flatMap(team => [
    { id: team.id, heading: `Company team: ${team.name}`, content: `${team.description || 'No description recorded.'}\n${team.assignments.length ? `${team.assignments.length} current assignments recorded; consult individual assignment evidence for people.` : 'No current assignments recorded.'}`,
      updatedAt: team.updatedAt.toISOString() },
    ...team.assignments.map(item => ({ id: `${team.id}:${item.user.username}`, heading: `Company assignment: ${team.name}`,
      content: `${item.user.firstName} ${item.user.lastName} (@${item.user.username}): ${item.assignment}\nThis is a company-team assignment, not proof of a project responsibility or project access.`,
      updatedAt: item.updatedAt.toISOString() }))
  ]);
  return rows.map(row => ({ ...row, score: words.filter(word => `${row.heading} ${row.content}`.toLowerCase().includes(word)).length }))
    .filter(row => row.score > 0).sort((a, b) => b.score - a.score || a.id.localeCompare(b.id)).slice(0, 8)
    .map(({ score, ...row }) => ({ ...row, heading: Array.from(row.heading).slice(0, 200).join(''),
      content: excerpt(row.content) }));
}
module.exports = { companyContext, companySources };
