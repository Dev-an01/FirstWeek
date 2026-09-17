ALTER TABLE "projects" ADD COLUMN "knowledgeVersion" INTEGER NOT NULL DEFAULT 0;
CREATE TABLE "project_conversations" (
  "companyId" TEXT NOT NULL,
  "projectId" TEXT NOT NULL,
  "userId" TEXT NOT NULL,
  "id" TEXT NOT NULL,
  "title" TEXT NOT NULL DEFAULT 'New conversation',
  "turns" JSONB NOT NULL DEFAULT '[]',
  "knowledgeHash" TEXT NOT NULL,
  "version" INTEGER NOT NULL DEFAULT 0,
  "pendingId" TEXT,
  "pendingQuestion" TEXT,
  "pendingAt" TIMESTAMP(3),
  "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updatedAt" TIMESTAMP(3) NOT NULL,
  PRIMARY KEY ("companyId", "projectId", "userId", "id"),
  FOREIGN KEY ("companyId", "projectId", "userId") REFERENCES "project_members"("companyId", "projectId", "userId") ON UPDATE CASCADE ON DELETE CASCADE
);
