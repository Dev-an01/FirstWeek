CREATE TABLE "project_documents" (
  "companyId" TEXT NOT NULL,
  "projectId" TEXT NOT NULL,
  "id" TEXT NOT NULL,
  "title" TEXT NOT NULL,
  "filename" TEXT NOT NULL,
  "mediaType" TEXT NOT NULL,
  "content" TEXT NOT NULL,
  "sha256" TEXT NOT NULL,
  "byteSize" INTEGER NOT NULL,
  "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updatedAt" TIMESTAMP(3) NOT NULL,
  CONSTRAINT "project_documents_pkey" PRIMARY KEY ("companyId", "projectId", "id"),
  CONSTRAINT "project_documents_project_fkey" FOREIGN KEY ("companyId", "projectId") REFERENCES "projects"("companyId", "id") ON DELETE CASCADE ON UPDATE CASCADE
);

CREATE TABLE "project_document_chunks" (
  "companyId" TEXT NOT NULL,
  "projectId" TEXT NOT NULL,
  "documentId" TEXT NOT NULL,
  "position" INTEGER NOT NULL,
  "heading" TEXT NOT NULL,
  "content" TEXT NOT NULL,
  CONSTRAINT "project_document_chunks_pkey" PRIMARY KEY ("companyId", "projectId", "documentId", "position"),
  CONSTRAINT "project_document_chunks_document_fkey" FOREIGN KEY ("companyId", "projectId", "documentId") REFERENCES "project_documents"("companyId", "projectId", "id") ON DELETE CASCADE ON UPDATE CASCADE
);

CREATE INDEX "project_documents_companyId_projectId_createdAt_idx" ON "project_documents"("companyId", "projectId", "createdAt");
