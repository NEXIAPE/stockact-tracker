/** Prepara un estado de demo: procesa la reunión, aprueba propuestas BPMN y genera el procedimiento. */
import { prisma } from "../src/lib/db";
import { processMeeting } from "../src/core/ingest/pipeline";
import { approveProposal } from "../src/core/ingest/proposals";
import { generateProcedure } from "../src/core/ingest/procedure";
import { analyzeProcess } from "../src/core/ingest/analyze";

async function main() {
  process.env.LLM_PROVIDER = "mock";
  const meeting = await prisma.meeting.findFirstOrThrow({ orderBy: { createdAt: "asc" } });
  await processMeeting(meeting.id);
  const proposals = await prisma.changeProposal.findMany({ where: { meetingId: meeting.id, status: "pending" } });
  for (const p of proposals) await approveProposal(p.id, "demo@nexia.fit");
  const procId = await generateProcedure(meeting.processId);
  const recs = await analyzeProcess(meeting.processId);
  console.log(`✔ Demo lista: ${proposals.length} propuestas aprobadas, procedimiento ${procId}, ${recs} recomendaciones.`);
  await prisma.$disconnect();
}
main().catch(async (e) => {
  console.error(e);
  await prisma.$disconnect();
  process.exit(1);
});
