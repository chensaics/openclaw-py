"""Feishu Docx operations — table creation, file/image upload, permission management.

Ported from ``extensions/feishu/src/tools/docx.ts``.

Provides the ``feishu_doc`` tool actions for:
- Docx table creation (``create_table``, ``write_table_cells``, ``create_table_with_values``)
- Image and file uploads (``upload_image``, ``upload_file``)
- Document permission grants (optional owner permission fields)
- Sequential block insertion to preserve ordering
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class DocxTableCell:
    """A single cell value in a Docx table."""

    row: int
    col: int
    text: str


@dataclass
class DocxTable:
    """A Docx table specification."""

    rows: int
    cols: int
    cells: list[DocxTableCell] = field(default_factory=list)
    header_row: list[str] | None = None


@dataclass
class DocxUploadResult:
    """Result of a file/image upload to Feishu Docx."""

    file_token: str = ""
    file_key: str = ""
    success: bool = False
    error: str = ""


@dataclass
class DocxPermissionGrant:
    """Permission grant for a Feishu document."""

    member_type: str = "openchat"  # "openchat" | "userid" | "email" | "department"
    member_id: str = ""
    perm: str = "view"  # "view" | "edit" | "full_access"


class FeishuDocxClient:
    """Client for Feishu Docx API operations."""

    def __init__(self, api_base: str, access_token: str) -> None:
        self._api_base = api_base
        self._access_token = access_token

    async def create_table(
        self,
        document_id: str,
        rows: int,
        cols: int,
        *,
        block_id: str = "",
        index: int = -1,
    ) -> dict[str, Any]:
        """Create an empty table in a Docx document."""
        if not document_id:
            return {"error": "document_id is required"}

        block_body = {
            "block_type": 31,  # Table block type
            "table": {
                "property": {"row_size": rows, "column_size": cols},
            },
        }

        return await self._create_block(document_id, block_body, block_id=block_id, index=index)

    async def write_table_cells(
        self,
        document_id: str,
        table_id: str,
        cells: list[DocxTableCell],
    ) -> dict[str, Any]:
        """Write values to table cells."""
        if not document_id or not table_id:
            return {"error": "document_id and table_id are required"}

        results: list[dict[str, Any]] = []
        # Write cells sequentially to preserve order
        for cell in cells:
            cell_block_id = f"{table_id}_r{cell.row}_c{cell.col}"
            text_block = {
                "block_type": 2,  # Text block
                "text": {
                    "elements": [{"text_run": {"content": cell.text}}],
                },
            }
            result = await self._create_block(document_id, text_block, block_id=cell_block_id)
            results.append(result)

        return {"results": results, "count": len(results)}

    async def create_table_with_values(
        self,
        document_id: str,
        header: list[str],
        rows: list[list[str]],
        *,
        block_id: str = "",
        index: int = -1,
    ) -> dict[str, Any]:
        """Create a table pre-filled with header and row data."""
        total_rows = 1 + len(rows)
        cols = len(header)

        table_result = await self.create_table(document_id, total_rows, cols, block_id=block_id, index=index)
        table_id = table_result.get("block_id", "")
        if not table_id:
            return table_result

        cells: list[DocxTableCell] = []
        for col_i, h in enumerate(header):
            cells.append(DocxTableCell(row=0, col=col_i, text=h))
        for row_i, row in enumerate(rows):
            for col_i, val in enumerate(row):
                cells.append(DocxTableCell(row=row_i + 1, col=col_i, text=val))

        return await self.write_table_cells(document_id, table_id, cells)

    async def upload_image(
        self,
        document_id: str,
        image_data: bytes,
        *,
        filename: str = "image.png",
        content_type: str = "image/png",
        block_id: str = "",
    ) -> DocxUploadResult:
        """Upload an image to a Docx document."""
        if not document_id:
            return DocxUploadResult(error="document_id is required")

        try:
            import aiohttp

            url = f"{self._api_base}/open-apis/drive/v1/medias/upload_all"
            headers = {"Authorization": f"Bearer {self._access_token}"}

            form = aiohttp.FormData()
            form.add_field("file_name", filename)
            form.add_field("parent_type", "docx_image")
            form.add_field("parent_node", document_id)
            form.add_field("size", str(len(image_data)))
            form.add_field(
                "file",
                image_data,
                filename=filename,
                content_type=content_type,
            )

            async with aiohttp.ClientSession() as session:
                async with session.post(url, data=form, headers=headers) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        file_token = data.get("data", {}).get("file_token", "")
                        return DocxUploadResult(file_token=file_token, success=True)
                    else:
                        err = await resp.text()
                        return DocxUploadResult(error=f"Upload failed: {resp.status} {err[:200]}")

        except ImportError:
            return DocxUploadResult(error="aiohttp required for uploads")
        except Exception as exc:
            return DocxUploadResult(error=str(exc))

    async def upload_file(
        self,
        document_id: str,
        file_data: bytes,
        *,
        filename: str = "file",
        content_type: str = "application/octet-stream",
    ) -> DocxUploadResult:
        """Upload a generic file to a Docx document."""
        if not document_id:
            return DocxUploadResult(error="document_id is required")

        try:
            import aiohttp

            url = f"{self._api_base}/open-apis/drive/v1/medias/upload_all"
            headers = {"Authorization": f"Bearer {self._access_token}"}

            form = aiohttp.FormData()
            form.add_field("file_name", filename)
            form.add_field("parent_type", "docx_file")
            form.add_field("parent_node", document_id)
            form.add_field("size", str(len(file_data)))
            form.add_field(
                "file",
                file_data,
                filename=filename,
                content_type=content_type,
            )

            async with aiohttp.ClientSession() as session:
                async with session.post(url, data=form, headers=headers) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        file_token = data.get("data", {}).get("file_token", "")
                        return DocxUploadResult(file_token=file_token, success=True)
                    else:
                        err = await resp.text()
                        return DocxUploadResult(error=f"Upload failed: {resp.status} {err[:200]}")

        except ImportError:
            return DocxUploadResult(error="aiohttp required for uploads")
        except Exception as exc:
            return DocxUploadResult(error=str(exc))

    async def grant_permission(
        self,
        document_token: str,
        grant: DocxPermissionGrant,
        *,
        doc_type: str = "docx",
    ) -> dict[str, Any]:
        """Grant permissions on a Feishu document."""
        try:
            import aiohttp

            url = f"{self._api_base}/open-apis/drive/v1/permissions/{document_token}/members"
            headers = {
                "Authorization": f"Bearer {self._access_token}",
                "Content-Type": "application/json",
            }
            params = {"type": doc_type}
            payload = {
                "member_type": grant.member_type,
                "member_id": grant.member_id,
                "perm": grant.perm,
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, headers=headers, params=params) as resp:
                    data = await resp.json()
                    if resp.status == 200 and data.get("code") == 0:
                        return {"success": True, "data": data.get("data", {})}
                    return {"success": False, "error": data.get("msg", str(resp.status))}

        except ImportError:
            return {"success": False, "error": "aiohttp required"}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    async def _create_block(
        self,
        document_id: str,
        block: dict[str, Any],
        *,
        block_id: str = "",
        index: int = -1,
    ) -> dict[str, Any]:
        """Create a block in a Docx document (sequential to preserve order)."""
        try:
            import aiohttp

            parent = block_id or document_id
            url = f"{self._api_base}/open-apis/docx/v1/documents/{document_id}/blocks/{parent}/children"
            headers = {
                "Authorization": f"Bearer {self._access_token}",
                "Content-Type": "application/json",
            }
            payload: dict[str, Any] = {"children": [block]}
            if index >= 0:
                payload["index"] = index

            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, headers=headers) as resp:
                    data = await resp.json()
                    if resp.status == 200 and data.get("code") == 0:
                        children = data.get("data", {}).get("children", [])
                        bid = children[0].get("block_id", "") if children else ""
                        return {"success": True, "block_id": bid}
                    return {"success": False, "error": data.get("msg", str(resp.status))}

        except ImportError:
            return {"success": False, "error": "aiohttp required"}
        except Exception as exc:
            return {"success": False, "error": str(exc)}
