import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { historyApi } from '../../../api/history';
import { ShareImageButton } from '../ShareImageButton';

vi.mock('../../../api/history', () => ({
  historyApi: {
    getShareImage: vi.fn(),
  },
}));

const mockedGetShareImage = vi.mocked(historyApi.getShareImage);

describe('ShareImageButton', () => {
  beforeEach(() => {
    mockedGetShareImage.mockReset();
    vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:share-image');
    vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => undefined);
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => undefined);
    Object.defineProperty(navigator, 'share', { configurable: true, value: undefined });
    Object.defineProperty(navigator, 'canShare', { configurable: true, value: undefined });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('downloads the generated PNG when native file sharing is unavailable', async () => {
    mockedGetShareImage.mockResolvedValue(new Blob(['png'], { type: 'image/png' }));

    render(
      <ShareImageButton
        recordId={17}
        reportTitle="中钨高新-000657"
        reportLanguage="zh"
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: '分享' }));

    await waitFor(() => expect(mockedGetShareImage).toHaveBeenCalledWith(17));
    await waitFor(() => expect(HTMLAnchorElement.prototype.click).toHaveBeenCalled());
    expect(screen.getByRole('button', { name: '已生成' })).toBeInTheDocument();
  });

  it('uses native file sharing when the browser supports it', async () => {
    const nativeShare = vi.fn().mockResolvedValue(undefined);
    mockedGetShareImage.mockResolvedValue(new Blob(['png'], { type: 'image/png' }));
    Object.defineProperty(navigator, 'share', { configurable: true, value: nativeShare });
    Object.defineProperty(navigator, 'canShare', { configurable: true, value: () => true });

    render(
      <ShareImageButton
        recordId={18}
        reportTitle="A股市场复盘"
        reportLanguage="zh"
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: '分享' }));

    await waitFor(() => expect(nativeShare).toHaveBeenCalledTimes(1));
    const sharePayload = nativeShare.mock.calls[0][0];
    expect(sharePayload.title).toBe('A股市场复盘');
    expect(sharePayload.files[0].name).toBe('A股市场复盘-18.png');
  });

  it('downloads the PNG when native file sharing rejects', async () => {
    const nativeShare = vi.fn().mockRejectedValue(new Error('activation expired'));
    mockedGetShareImage.mockResolvedValue(new Blob(['png'], { type: 'image/png' }));
    Object.defineProperty(navigator, 'share', { configurable: true, value: nativeShare });
    Object.defineProperty(navigator, 'canShare', { configurable: true, value: () => true });

    render(
      <ShareImageButton
        recordId={20}
        reportTitle="A股市场复盘"
        reportLanguage="zh"
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: '分享' }));

    await waitFor(() => expect(nativeShare).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(HTMLAnchorElement.prototype.click).toHaveBeenCalledTimes(1));
    expect(screen.getByRole('button', { name: '已生成' })).toBeInTheDocument();
  });

  it('shows a retryable error state when image generation fails', async () => {
    mockedGetShareImage.mockRejectedValue(new Error('renderer unavailable'));

    render(
      <ShareImageButton
        recordId={19}
        reportTitle="中钨高新"
        reportLanguage="zh"
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: '分享' }));

    expect(await screen.findByRole('button', { name: '重试' })).toBeInTheDocument();
  });
});
