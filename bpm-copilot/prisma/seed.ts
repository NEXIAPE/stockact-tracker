import { PrismaClient } from "@prisma/client";

const prisma = new PrismaClient();

const SAMPLE_TRANSCRIPT = `María González: Buenos días a todos, gracias por conectarse. Soy María González, Gerente de Finanzas. El objetivo de hoy es levantar el proceso de aprobación de facturas de proveedores.
Juan Pérez: Hola, soy Juan Pérez, Coordinador del área de Cuentas por Pagar. Hoy el proceso arranca cuando el proveedor envía la factura por correo a Cuentas por Pagar.
Pedro Ramírez: Buenas, Pedro Ramírez, Analista de Tesorería. Yo me encargo de la programación de pagos.
María González: De acuerdo, entonces el evento de inicio es la recepción de la factura por correo.
Pedro Ramírez: Cuentas por Pagar registra la factura en SAP y valida que tenga orden de compra asociada.
Juan Pérez: Si no tiene orden de compra, se devuelve al proveedor. Eso es una decisión: acordamos que sin orden de compra no se procesa.
María González: Decidimos que el umbral de aprobación gerencial será de 5000 dólares. Por encima de eso aprueba el Gerente Financiero.
Pedro Ramírez: Un riesgo importante es que los proveedores envían facturas a correos personales y se pierden. Eso genera retrasos en el pago.
Juan Pérez: Pendiente: Pedro deberá preparar el catálogo de proveedores actualizado para el viernes.
María González: También queda como pendiente que Tesorería revise los plazos de pago con cada proveedor.
Pedro Ramírez: Una vez aprobada, Tesorería programa el pago en el sistema y notifica al proveedor.
María González: Acordamos que el proceso termina cuando se confirma el pago al proveedor.`;

async function main() {
  const project = await prisma.project.create({
    data: {
      name: "Transformación Cuentas por Pagar",
      sponsor: "Dirección Financiera",
      status: "active",
      startDate: new Date("2026-05-01"),
    },
  });

  const process = await prisma.process.create({
    data: {
      projectId: project.id,
      name: "Aprobación de facturas de proveedores",
      code: "FIN-PD001",
      area: "Finanzas",
      objective: "Estandarizar y agilizar la aprobación y pago de facturas de proveedores.",
      scope: "Desde la recepción de la factura hasta la confirmación del pago.",
      status: "discovery",
    },
  });

  await prisma.meeting.create({
    data: {
      processId: process.id,
      title: "Levantamiento inicial con Cuentas por Pagar",
      date: new Date("2026-05-12"),
      transcript: SAMPLE_TRANSCRIPT,
    },
  });

  console.log("✔ Seed completo.");
  console.log(`  Proyecto: ${project.name}`);
  console.log(`  Proceso:  ${process.name}`);
  console.log("  Abre la reunión y pulsa «Procesar transcripción».");
}

main()
  .then(() => prisma.$disconnect())
  .catch(async (e) => {
    console.error(e);
    await prisma.$disconnect();
    process.exit(1);
  });
