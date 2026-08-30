"use client";

/**
 * TopNav — global navigation bar matching the Figma design.
 */

interface TopNavProps {
  hotspotsCount: number;
  lastFetched: Date | null;
}

export default function TopNav({ hotspotsCount, lastFetched }: TopNavProps) {
  return (
    <nav className="top-nav">
      {/* Logo */}
      <div className="nav-logo">
        <div className="nav-logo-icon">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2z"/>
            <circle cx="12" cy="12" r="4" fill="white" stroke="none"/>
            <path d="M12 2v4M12 18v4M2 12h4M18 12h4"/>
          </svg>
        </div>
        <span className="nav-logo-text">ThermaSense</span>
      </div>

      {/* Search */}
      <div className="nav-search">
        <svg className="nav-search-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
        </svg>
        <input
          type="text"
          placeholder="Search coordinates, region or event ID..."
          id="global-search"
        />
      </div>

      <div className="nav-spacer" />

      {/* Live Badge */}
      <div className="nav-live-badge">
        <div className="nav-live-dot" />
        LIVE DATA
      </div>

      {/* Icon Buttons */}
      <button className="nav-icon-btn" aria-label="Notifications" title="Notifications">
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/>
          <path d="M13.73 21a2 2 0 0 1-3.46 0"/>
        </svg>
      </button>

      <button className="nav-icon-btn" aria-label="Settings" title="Settings">
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <circle cx="12" cy="12" r="3"/>
          <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>
        </svg>
      </button>

      {/* Avatar */}
      <div className="nav-avatar" title={`${hotspotsCount} observations loaded${lastFetched ? `, last at ${lastFetched.toLocaleTimeString()}` : ''}`}>
        TS
      </div>
    </nav>
  );
}
