// Phase 2: frontend agent builds this page
// Use mock data until Phase 4 (api-developer wires real API)
export default function HomePage() {
  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Research Query</h1>
      {/* TODO (frontend agent): Add SearchForm and ResultsPanel components */}
      <p className="text-gray-500">Frontend agent: implement search form and results panel here.</p>
    </div>
  );
}
