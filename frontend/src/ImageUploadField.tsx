import { useEffect, useRef, useState } from "react";
import { Upload, X } from "lucide-react";
import { backendApiUrl } from "./apiConfig";
import { AuthExpiredError } from "./db";

export type UploadedImage = {
  id: string;
  fileName: string;
  url: string;
};

async function uploadSiteImage(file: File, documentType: string, ownerId: string): Promise<UploadedImage> {
  const formData = new FormData();
  formData.append("documentType", documentType);
  formData.append("ownerId", ownerId);
  formData.append("file", file);
  let response: Response;
  try {
    response = await fetch(backendApiUrl("/api/documents/upload/"), {
      method: "POST",
      credentials: "include",
      body: formData,
    });
  } catch {
    throw new Error("图片上传失败，请检查网络后重试。");
  }
  let payload: { data?: { id: string; fileName: string; url?: string }; detail?: string } = {};
  try {
    payload = (await response.json()) as typeof payload;
  } catch {
    // 非 JSON
  }
  if (response.status === 401) throw new AuthExpiredError();
  if (!response.ok || !payload.data?.id) throw new Error(payload.detail || "图片保存失败。");
  const url = payload.data.url || `/api/documents/${payload.data.id}/`;
  return { id: payload.data.id, fileName: payload.data.fileName, url };
}

function previewSrc(url?: string) {
  const value = (url || "").trim();
  if (!value) return "";
  if (value.startsWith("http://") || value.startsWith("https://") || value.startsWith("blob:")) return value;
  if (value.startsWith("/api/")) return backendApiUrl(value);
  return value;
}

export function ImageUploadField({
  label,
  ownerId,
  documentType,
  fileId,
  url,
  disabled,
  accept = "image/png,image/jpeg,image/webp,image/bmp",
  onChange,
  onError,
}: {
  label: string;
  ownerId: string;
  documentType: string;
  fileId?: string;
  url?: string;
  disabled?: boolean;
  accept?: string;
  onChange: (next: { fileId: string; url: string; fileName?: string }) => void;
  onError?: (message: string) => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const [fileName, setFileName] = useState("");
  const [broken, setBroken] = useState(false);
  const src = previewSrc(url);

  useEffect(() => {
    setBroken(false);
  }, [src]);

  async function handleFile(file: File | undefined) {
    if (!file || disabled) return;
    if (!ownerId) {
      onError?.("请先保存站点基本信息后再上传图片。");
      return;
    }
    setUploading(true);
    setFileName(file.name);
    try {
      const saved = await uploadSiteImage(file, documentType, ownerId);
      setBroken(false);
      onChange({ fileId: saved.id, url: saved.url, fileName: saved.fileName });
    } catch (error) {
      if (error instanceof AuthExpiredError) throw error;
      onError?.(error instanceof Error ? error.message : "图片上传失败。");
    } finally {
      setUploading(false);
    }
  }

  return (
    <div className="image-upload-field span-2">
      <span>{label}</span>
      <div className="image-upload-row">
        <div className="image-upload-preview">
          {src && !broken ? (
            <img key={src} src={src} alt={label} onError={() => setBroken(true)} />
          ) : (
            <em>{broken ? "图片无法显示" : "暂无图片"}</em>
          )}
        </div>
        <div className="image-upload-controls">
          <div className="file-picker">
            <input
              ref={inputRef}
              type="file"
              accept={accept}
              className="file-picker-input"
              tabIndex={-1}
              aria-hidden="true"
              disabled={disabled || uploading || !ownerId}
              onChange={(event) => {
                void handleFile(event.target.files?.[0]);
                event.target.value = "";
              }}
            />
            <button
              type="button"
              className="ghost file-picker-trigger"
              disabled={disabled || uploading || !ownerId}
              onClick={() => inputRef.current?.click()}
            >
              <Upload size={16} />
              {uploading ? "上传中…" : fileId || url ? "更换图片" : "上传图片"}
            </button>
            <span className={`file-picker-name${fileName || url ? "" : " is-empty"}`}>
              {uploading ? "正在上传…" : fileName || (url ? "已配置图片" : "未选择文件")}
            </span>
            {(fileId || url) && !disabled ? (
              <button
                type="button"
                className="file-picker-clear"
                aria-label="清除图片"
                onClick={() => {
                  setFileName("");
                  onChange({ fileId: "", url: "/image/wx.png" });
                }}
              >
                <X size={14} />
              </button>
            ) : null}
          </div>
          <p className="official-form-hint">支持 PNG / JPG / WebP，上传后保存到服务器；官网前台通过 `/api/documents/…` 访问。</p>
        </div>
      </div>
    </div>
  );
}
