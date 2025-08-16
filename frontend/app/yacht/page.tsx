import Link from 'next/link';

export default function YachtSoon() {
  return (
    <main className="content">
      <section className="hero hero--tight">
        <h1>Yacht</h1>
        <p>Handpicked yacht charters and repositioning deals are coming soon.</p>
        <div className="hero__cta">
          <Link className="btn btn--primary" href="/private-jet">Browse Private Jets</Link>
        </div>
      </section>
    </main>
  );
}