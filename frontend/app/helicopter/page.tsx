// app/yacht/page.tsx
export const dynamic = 'force-static';
export default function YachtComingSoon() {
  return (
    <main className="hero">
      <h1>Yacht — Coming Soon</h1>
      <p className="center" style={{opacity:.8, marginTop:8}}>
        Sneak peeks of repositioning trips and last-minute charters soon.
      </p>
      <p style={{marginTop:20}}>
        <a href="/private-jet" className="btn btn--primary">Browse Private Jets</a>
      </p>
    </main>
  );
}