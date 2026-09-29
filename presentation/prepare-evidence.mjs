import { readFile, writeFile, mkdir, cp } from 'node:fs/promises';
// Copy original recorded points and reports; no interpolation, retiming, labels, or generated measurements.
const source = JSON.parse(await readFile(new URL('../frontend/data/slac-001.json', import.meta.url), 'utf8'));
const data = {
  rf: source.plots.rf,
  beam: source.plots.beam.filter(p => p.channel === 'BPMS:LTUH:250:X'),
  charge: source.plots.beam.filter(p => ['BPMS:DMPH:502:TMIT', 'BPMS:LTUH:250:TMIT'].includes(p.channel)),
  runs: source.runs.map(r => ({ id: r.id, question: r.question, latency: r.wall_latency_s, report: r.report })),
};
await writeFile(new URL('src/evidence.json', import.meta.url), JSON.stringify(data));
// Ship the existing console at a relative URL so the presentation is portable.
await mkdir(new URL('public/console/', import.meta.url), { recursive: true });
for (const name of ['index.html', 'assets', 'data', '.nojekyll']) {
  await cp(new URL('../frontend/' + name, import.meta.url), new URL('public/console/' + name, import.meta.url), { recursive: true });
}
