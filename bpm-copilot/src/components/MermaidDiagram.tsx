"use client";

import { useEffect, useRef, useState } from "react";

/**
 * Render visual de un diagrama Mermaid en cliente.
 * Carga mermaid dinámicamente (solo en el navegador) para no engordar el bundle
 * del servidor. Si el render falla, muestra el código como fallback.
 */
export default function MermaidDiagram({ chart }: { chart: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const mermaid = (await import("mermaid")).default;
        mermaid.initialize({
          startOnLoad: false,
          theme: "neutral",
          securityLevel: "strict",
          flowchart: { useMaxWidth: true, htmlLabels: true, curve: "basis" },
        });
        const id = "mmd-" + Math.random().toString(36).slice(2);
        const { svg } = await mermaid.render(id, chart);
        if (!cancelled && ref.current) ref.current.innerHTML = svg;
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : "Error al renderizar el diagrama");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [chart]);

  if (error) {
    return (
      <pre className="overflow-x-auto rounded bg-slate-900 p-3 text-xs text-slate-100">
        <code>{chart}</code>
      </pre>
    );
  }

  return <div ref={ref} className="mermaid-container w-full overflow-x-auto" />;
}
