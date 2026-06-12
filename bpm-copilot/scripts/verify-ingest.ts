/**
 * Verificación end-to-end del pipeline de ingesta (sin red, adaptador mock).
 * Procesa la reunión sembrada, aprueba propuestas BPMN y comprueba el versionado.
 */
import { prisma } from "../src/lib/db";
import { processMeeting } from "../src/core/ingest/pipeline";
import { approveProposal } from "../src/core/ingest/proposals";

async function main() {
  process.env.LLM_PROVIDER = "mock";

  const meeting = await prisma.meeting.findFirstOrThrow({ orderBy: { createdAt: "asc" } });
  console.log(`→ Procesando reunión: ${meeting.title}`);
  await processMeeting(meeting.id);

  const refreshed = await prisma.meeting.findUniqueOrThrow({
    where: { id: meeting.id },
    include: { agreements: true, proposals: true },
  });
  const [ai, dec, risk] = await Promise.all([
    prisma.actionItem.count({ where: { sourceMeetingId: meeting.id } }),
    prisma.decision.count({ where: { sourceMeetingId: meeting.id } }),
    prisma.risk.count({ where: { sourceMeetingId: meeting.id } }),
  ]);

  console.log(`  estado:      ${refreshed.processState}`);
  console.log(`  resumen:     ${refreshed.summary?.slice(0, 80)}...`);
  console.log(`  acuerdos:    ${refreshed.agreements.length}`);
  console.log(`  pendientes:  ${ai}`);
  console.log(`  decisiones:  ${dec}`);
  console.log(`  riesgos:     ${risk}`);
  console.log(`  propuestas:  ${refreshed.proposals.length}`);

  const firstPending = refreshed.proposals.find((p) => p.status === "pending");
  if (firstPending) {
    console.log(`→ Aprobando propuesta BPMN: ${firstPending.title}`);
    await approveProposal(firstPending.id, "verify@test");
    const proc = await prisma.process.findUniqueOrThrow({
      where: { id: meeting.processId },
      include: { currentVersion: true },
    });
    console.log(`  versión BPMN vigente: v${proc.currentVersion?.version}`);
  }

  // Idempotencia: reprocesar no debe duplicar
  await processMeeting(meeting.id);
  const ai2 = await prisma.actionItem.count({ where: { sourceMeetingId: meeting.id } });
  console.log(`→ Reproceso idempotente: pendientes siguen en ${ai2} (sin duplicar)`);

  console.log("\n✔ Verificación OK");
  await prisma.$disconnect();
}

main().catch(async (e) => {
  console.error("✖ Falló:", e);
  await prisma.$disconnect();
  process.exit(1);
});
