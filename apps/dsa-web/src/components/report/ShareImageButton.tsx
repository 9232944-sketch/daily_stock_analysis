import type React from 'react';
import { useCallback, useEffect, useRef, useState } from 'react';
import { Check, Loader2, Share2, TriangleAlert } from 'lucide-react';
import { historyApi } from '../../api/history';
import type { ReportLanguage } from '../../types/analysis';
import { getReportText, normalizeReportLanguage } from '../../utils/reportLanguage';
import { Tooltip } from '../common/Tooltip';

type ShareState = 'idle' | 'loading' | 'success' | 'error';

interface ShareImageButtonProps {
  recordId?: number;
  reportTitle: string;
  reportLanguage?: ReportLanguage;
  className?: string;
}

const safeFilenamePart = (value: string): string => {
  const normalized = value.trim().replace(/[\\/:*?"<>|]+/g, '-').replace(/\s+/g, '-');
  return normalized.slice(0, 72) || 'report';
};

const downloadBlob = (blob: Blob, filename: string): void => {
  const objectUrl = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = objectUrl;
  anchor.download = filename;
  anchor.click();
  window.setTimeout(() => URL.revokeObjectURL(objectUrl), 0);
};

export const ShareImageButton: React.FC<ShareImageButtonProps> = ({
  recordId,
  reportTitle,
  reportLanguage = 'zh',
  className = '',
}) => {
  const text = getReportText(normalizeReportLanguage(reportLanguage));
  const [state, setState] = useState<ShareState>('idle');
  const resetTimerRef = useRef<number | null>(null);

  useEffect(() => () => {
    if (resetTimerRef.current !== null) {
      window.clearTimeout(resetTimerRef.current);
    }
  }, []);

  const scheduleReset = useCallback(() => {
    if (resetTimerRef.current !== null) {
      window.clearTimeout(resetTimerRef.current);
    }
    resetTimerRef.current = window.setTimeout(() => setState('idle'), 2200);
  }, []);

  const handleShare = useCallback(async () => {
    if (recordId === undefined || state === 'loading') return;
    setState('loading');

    try {
      const blob = await historyApi.getShareImage(recordId);
      const filename = `${safeFilenamePart(reportTitle)}-${recordId}.png`;
      const file = new File([blob], filename, { type: 'image/png' });
      const canShareFile = typeof navigator.share === 'function'
        && typeof navigator.canShare === 'function'
        && navigator.canShare({ files: [file] });

      if (canShareFile) {
        try {
          await navigator.share({
            files: [file],
            title: reportTitle,
          });
        } catch (error) {
          if (error instanceof DOMException && error.name === 'AbortError') {
            setState('idle');
            return;
          }
          throw error;
        }
      } else {
        downloadBlob(blob, filename);
      }

      setState('success');
      scheduleReset();
    } catch (error) {
      console.error('Generate share image failed:', error);
      setState('error');
    }
  }, [recordId, reportTitle, scheduleReset, state]);

  if (recordId === undefined) return null;

  const tooltipText = state === 'loading'
    ? text.generatingShareImage
    : state === 'success'
      ? text.shareImageReady
      : state === 'error'
        ? text.shareImageFailed
        : text.generateShareImage;

  return (
    <Tooltip content={tooltipText}>
      <span className="inline-flex shrink-0">
        <button
          type="button"
          onClick={() => void handleShare()}
          disabled={state === 'loading'}
          className={`home-surface-button flex h-10 shrink-0 items-center justify-center gap-2 whitespace-nowrap rounded-lg px-3 text-sm font-medium text-secondary-text hover:text-foreground disabled:opacity-50 ${className}`}
          aria-label={tooltipText}
        >
          {state === 'loading' ? <Loader2 className="h-5 w-5 animate-spin" aria-hidden="true" /> : null}
          {state === 'success' ? <Check className="h-5 w-5 text-success" aria-hidden="true" /> : null}
          {state === 'error' ? <TriangleAlert className="h-5 w-5 text-danger" aria-hidden="true" /> : null}
          {state === 'idle' ? <Share2 className="h-5 w-5" aria-hidden="true" /> : null}
          <span>{tooltipText}</span>
        </button>
      </span>
    </Tooltip>
  );
};
