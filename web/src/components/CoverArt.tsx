import { useEffect, useState } from 'react';
import { fetchAuthorizedBlob } from '@/api/client';
import { cn } from '@/lib/utils';

interface CoverArtProps {
  coverUrl?: string | null;
  className?: string;
  alt?: string;
}

function isRemoteCover(coverUrl: string): boolean {
  return /^https?:\/\//i.test(coverUrl);
}

export function CoverArt({ coverUrl, className, alt = '' }: CoverArtProps) {
  const [src, setSrc] = useState<string | null>(null);

  useEffect(() => {
    if (!coverUrl) {
      setSrc(null);
      return;
    }
    if (isRemoteCover(coverUrl)) {
      setSrc(coverUrl);
      return;
    }

    let cancelled = false;
    let objectUrl: string | null = null;

    void fetchAuthorizedBlob(coverUrl)
      .then((blob) => {
        const url = URL.createObjectURL(blob);
        if (cancelled) {
          URL.revokeObjectURL(url);
          return;
        }
        objectUrl = url;
        setSrc(url);
      })
      .catch(() => {
        if (!cancelled) {
          setSrc(null);
        }
      });

    return () => {
      cancelled = true;
      if (objectUrl) {
        URL.revokeObjectURL(objectUrl);
      }
    };
  }, [coverUrl]);

  if (!src) {
    return <div className={cn('shrink-0 rounded bg-surface-border', className)} aria-hidden />;
  }

  return <img src={src} alt={alt} className={cn('shrink-0 rounded object-cover', className)} />;
}
