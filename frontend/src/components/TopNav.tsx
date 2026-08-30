"use client";

/**
 * TopNav — global navigation bar matching the Figma design with Live Operational Alerts Center.
 */

import { useState, useEffect, useRef } from "react";
import type { ThermalAlert } from "@/types/export";
import { fetchAlerts } from "@/services/api";

interface TopNavProps {
  hotspotsCount: number;
  lastFetched: Date | null;
  onSelectAlert?: (alert: ThermalAlert) => void;
}

export default function TopNav({
  hotspotsCount,
  lastFetched,
  onSelectAlert,
}: TopNavProps) {
  const [alerts, setAlerts] = useState<ThermalAlert[]>([]);
  const [alertsOpen, setAlertsOpen] = useState(false);
  const [loadingAlerts, setLoadingAlerts] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const loadAlerts = async () => {
    try {
      setLoadingAlerts(true);
      const res = await fetchAlerts(undefined, 20);
      setAlerts(res.alerts || []);
    } catch {
      // Non-blocking
    } finally {
      setLoadingAlerts(false);
    }
  };

  useEffect(() => {
    loadAlerts();
    const interval = setInterval(loadAlerts, 60000); // 1 min poll
    return () => clearInterval(interval);
  }, []);

  // Close on outside click
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (
        dropdownRef.current &&
        !dropdownRef.current.contains(event.target as Node)
      ) {
        setAlertsOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const criticalCount = alerts.filter((a) => a.severity === "CRITICAL").length;
  const warningCount = alerts.filter((a) => a.severity === "WARNING").length;

  return (
    <nav className="top-nav" style={{ position: "relative", zIndex: 1000 }}>
      {/* Logo */}
      <div className="nav-logo">
        <div className="nav-logo-icon">
          <svg
            width="18"
            height="18"
            viewBox="0 0 24 24"
            fill="none"
            stroke="white"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2z" />
            <circle cx="12" cy="12" r="4" fill="white" stroke="none" />
            <path d="M12 2v4M12 18v4M2 12h4M18 12h4" />
          </svg>
        </div>
        <span className="nav-logo-text">ThermaSense</span>
      </div>

      {/* Search */}
      <div className="nav-search">
        <svg
          className="nav-search-icon"
          width="14"
          height="14"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
        >
          <circle cx="11" cy="11" r="8" />
          <path d="m21 21-4.35-4.35" />
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
        LIVE SATELLITE
      </div>

      {/* Alerts Bell & Dropdown */}
      <div style={{ position: "relative" }} ref={dropdownRef}>
        <button
          className="nav-icon-btn"
          aria-label="Operational Alerts"
          title={`Thermal Alerts (${alerts.length})`}
          onClick={() => setAlertsOpen((prev) => !prev)}
          style={{ position: "relative" }}
          id="alerts-bell-btn"
        >
          <svg
            width="15"
            height="15"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
          >
            <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
            <path d="M13.73 21a2 2 0 0 1-3.46 0" />
          </svg>

          {alerts.length > 0 && (
            <span
              style={{
                position: "absolute",
                top: 4,
                right: 4,
                width: 8,
                height: 8,
                borderRadius: "50%",
                background: criticalCount > 0 ? "#ef4444" : "#f97316",
                boxShadow: `0 0 8px ${criticalCount > 0 ? "#ef4444" : "#f97316"}`,
              }}
            />
          )}
        </button>

        {/* Alerts Dropdown Drawer */}
        {alertsOpen && (
          <div
            style={{
              position: "absolute",
              top: "calc(100% + 8px)",
              right: 0,
              width: 360,
              maxHeight: 460,
              background: "#0d131f",
              border: "1px solid rgba(255, 255, 255, 0.12)",
              borderRadius: 12,
              boxShadow: "0 16px 36px rgba(0, 0, 0, 0.65)",
              overflow: "hidden",
              display: "flex",
              flexDirection: "column",
            }}
          >
            {/* Header */}
            <div
              style={{
                padding: "12px 16px",
                background: "rgba(255, 255, 255, 0.03)",
                borderBottom: "1px solid rgba(255, 255, 255, 0.08)",
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <span style={{ fontSize: 13, fontWeight: 700, color: "#f8fafc" }}>
                  Operational Thermal Alerts
                </span>
                <span
                  style={{
                    fontSize: 10,
                    fontWeight: 700,
                    padding: "2px 6px",
                    borderRadius: 10,
                    background: criticalCount > 0 ? "rgba(239, 68, 68, 0.2)" : "rgba(249, 115, 22, 0.2)",
                    color: criticalCount > 0 ? "#f87171" : "#fb923c",
                  }}
                >
                  {alerts.length} ACTIVE
                </span>
              </div>
              <button
                onClick={loadAlerts}
                style={{
                  background: "transparent",
                  border: "none",
                  color: "#94a3b8",
                  fontSize: 11,
                  cursor: "pointer",
                }}
              >
                {loadingAlerts ? "..." : "Refresh"}
              </button>
            </div>

            {/* List */}
            <div style={{ overflowY: "auto", padding: "8px 12px", display: "flex", flexDirection: "column", gap: 8 }}>
              {alerts.length === 0 ? (
                <div style={{ padding: "24px 12px", textAlign: "center", color: "#64748b", fontSize: 12 }}>
                  No active operational alerts. All thermal events are within normal operational limits.
                </div>
              ) : (
                alerts.map((a) => {
                  const isCrit = a.severity === "CRITICAL";
                  const isWarn = a.severity === "WARNING";
                  const badgeColor = isCrit ? "#ef4444" : isWarn ? "#f97316" : "#38bdf8";

                  return (
                    <div
                      key={a.alert_id}
                      onClick={() => {
                        onSelectAlert?.(a);
                        setAlertsOpen(false);
                      }}
                      style={{
                        padding: "10px 12px",
                        background: "rgba(255, 255, 255, 0.03)",
                        border: `1px solid ${isCrit ? "rgba(239, 68, 68, 0.3)" : "rgba(255, 255, 255, 0.08)"}`,
                        borderRadius: 8,
                        cursor: "pointer",
                        transition: "all 0.15s ease",
                      }}
                    >
                      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 4 }}>
                        <span
                          style={{
                            fontSize: 9,
                            fontWeight: 800,
                            padding: "2px 5px",
                            borderRadius: 4,
                            background: `${badgeColor}22`,
                            color: badgeColor,
                            letterSpacing: "0.05em",
                          }}
                        >
                          {a.severity}
                        </span>
                        {a.frp != null && (
                          <span style={{ fontSize: 11, fontWeight: 700, color: "#fb923c" }}>
                            {a.frp.toFixed(1)} MW
                          </span>
                        )}
                      </div>
                      <div style={{ fontSize: 12, fontWeight: 600, color: "#e2e8f0", marginBottom: 3 }}>
                        {a.title}
                      </div>
                      <div style={{ fontSize: 11, color: "#94a3b8", lineHeight: 1.4 }}>
                        {a.message}
                      </div>
                      <div style={{ fontSize: 10, color: "#64748b", marginTop: 6, display: "flex", justifyContent: "space-between" }}>
                        <span>Lat: {a.latitude.toFixed(3)}°, Lon: {a.longitude.toFixed(3)}°</span>
                        <span>{a.rule_name}</span>
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </div>
        )}
      </div>

      {/* Avatar */}
      <div
        className="nav-avatar"
        title={`${hotspotsCount} observations loaded${
          lastFetched ? `, last at ${lastFetched.toLocaleTimeString()}` : ""
        }`}
      >
        TS
      </div>
    </nav>
  );
}
