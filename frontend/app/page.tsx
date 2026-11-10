import styles from "./page.module.css";

export default function HomePage() {
  return (
    <main className={styles.frame}>
      <aside className={styles.sidebar} aria-label="Workspace navigation">
        <div className={styles.brand}>
          <span className={styles.mark}>L</span>
          <span>Local AI</span>
        </div>
        <button className={styles.newChat} type="button" disabled>
          <span aria-hidden="true">＋</span> New chat
        </button>
        <div className={styles.sidebarLabel}>WORKSPACE</div>
        <div className={styles.navItem}>⌕ <span>Search</span></div>
        <div className={styles.navItem}>▤ <span>Documents</span></div>
        <div className={styles.sidebarBottom}>
          <span className={styles.avatar}>L</span>
          <span>Local workspace</span>
          <span className={styles.statusDot} aria-label="Local runtime not connected yet" />
        </div>
      </aside>

      <section className={styles.main}>
        <header className={styles.topbar}>
          <span>Workspace <span className={styles.slash}>/</span> New chat</span>
          <span className={styles.localBadge}><span /> Local-first</span>
        </header>

        <div className={styles.content}>
          <div className={styles.eyebrow}>YOUR PRIVATE KNOWLEDGE SPACE</div>
          <h1>What would you like to understand?</h1>
          <p className={styles.intro}>Add your documents and ask questions. Your files and conversations stay on this computer.</p>

          <div className={styles.cards}>
            <article className={styles.card}>
              <span className={styles.cardIcon}>↥</span>
              <h2>Bring in your documents</h2>
              <p>PDF, Word, text, CSV, and Markdown support is coming with document ingestion.</p>
              <span className={styles.cardFoot}>DOCUMENT LIBRARY <span>01</span></span>
            </article>
            <article className={styles.card}>
              <span className={styles.cardIcon}>✳</span>
              <h2>Explore with local AI</h2>
              <p>Questions will be answered using your selected files and a model running locally.</p>
              <span className={styles.cardFoot}>PRIVATE BY DESIGN <span>02</span></span>
            </article>
            <article className={styles.card}>
              <span className={styles.cardIcon}>文</span>
              <h2>Work in your language</h2>
              <p>English and Hindi input and responses are planned for the first release.</p>
              <span className={styles.cardFoot}>ENGLISH · हिन्दी <span>03</span></span>
            </article>
          </div>

          <div className={styles.notice}>
            <span className={styles.noticeIcon}>◷</span>
            <div><strong>Workspace setup is underway</strong><span>Authentication, document indexing, and chat are added in separate, testable features.</span></div>
          </div>
          <div className={styles.composer} aria-disabled="true">
            <span>Chat will be available after local model setup</span>
            <button type="button" disabled aria-label="Send message">↑</button>
          </div>
          <p className={styles.caption}>Your documents will be processed and searched on this device.</p>
        </div>
      </section>
    </main>
  );
}
