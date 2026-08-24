"use client";

import { useCallback, useEffect, useState } from "react";
import { useAuth } from "@/components/auth-provider";
import { getCustomerBookings } from "./api";
import type { CustomerBookingSummary } from "./types";

export function useCustomerBookings({ polling = false }: { polling?: boolean } = {}) {
  const { user, loading: authLoading } = useAuth();
  const [bookings, setBookings] = useState<CustomerBookingSummary[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [loadedUserId, setLoadedUserId] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (!user) return;
    setLoading(true);
    try {
      setBookings(await getCustomerBookings());
      setLoadedUserId(user.id);
      setError("");
    } catch {
      setError("We couldn’t load your bookings. Please try again.");
    } finally {
      setLoading(false);
    }
  }, [user]);

  useEffect(() => {
    let active = true;
    if (authLoading) return;
    if (!user) return;
    const userId = user.id;
    async function load() {
      await Promise.resolve();
      if (!active) return;
      setLoading(true);
      setError("");
      try {
        const nextBookings = await getCustomerBookings();
        if (!active) return;
        setBookings(nextBookings);
        setLoadedUserId(userId);
        setError("");
      } catch {
        if (active) setError("We couldn’t load your bookings. Please try again.");
      } finally {
        if (active) {
          setLoadedUserId(userId);
          setLoading(false);
        }
      }
    }
    void load();
    return () => { active = false; };
  }, [authLoading, user]);

  useEffect(() => {
    if (!polling || !user) return;
    const timer = window.setInterval(() => {
      if (document.visibilityState === "visible") void refresh();
    }, 25_000);
    return () => window.clearInterval(timer);
  }, [polling, refresh, user]);

  return {
    bookings: user && loadedUserId === user.id ? bookings : [],
    loading: authLoading || (user !== null && !error && (loading || loadedUserId !== user.id)),
    error: user ? error : "",
    refresh,
  };
}
