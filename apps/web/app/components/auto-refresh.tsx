"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

export function AutoRefresh({ intervalSeconds = 20 }: { intervalSeconds?: number }) {
  const router = useRouter();
  const [countdown, setCountdown] = useState(intervalSeconds);

  useEffect(() => {
    const tick = setInterval(() => {
      setCountdown((current) => {
        if (current <= 1) {
          router.refresh();
          return intervalSeconds;
        }
        return current - 1;
      });
    }, 1000);
    return () => clearInterval(tick);
  }, [intervalSeconds, router]);

  return <p>自动刷新倒计时：{countdown}s</p>;
}
