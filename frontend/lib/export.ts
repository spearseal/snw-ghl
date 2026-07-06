/**
 * Client-side export utilities (CSV + Excel-compatible).
 * Excel uses SpreadsheetML XML — opens in Excel without extra dependencies.
 */

export interface ExportColumn<T> {
  key: keyof T | string;
  header: string;
  format?: (row: T) => string | number;
}

function cellValue<T>(row: T, col: ExportColumn<T>): string {
  if (col.format) return String(col.format(row));
  const key = col.key as keyof T;
  const val = row[key];
  return val == null ? '' : String(val);
}

function escapeCsv(value: string): string {
  if (/[",\n\r]/.test(value)) return `"${value.replace(/"/g, '""')}"`;
  return value;
}

export function exportToCsv<T>(rows: T[], columns: ExportColumn<T>[], filename: string): void {
  const header = columns.map((c) => escapeCsv(c.header)).join(',');
  const body = rows
    .map((row) => columns.map((col) => escapeCsv(cellValue(row, col))).join(','))
    .join('\n');
  const bom = '\uFEFF';
  downloadBlob(`${bom}${header}\n${body}`, `${filename}.csv`, 'text/csv;charset=utf-8');
}

export function exportToExcel<T>(rows: T[], columns: ExportColumn<T>[], filename: string): void {
  const headerRow = columns.map((c) => `<Cell><Data ss:Type="String">${xmlEscape(c.header)}</Data></Cell>`).join('');
  const dataRows = rows
    .map((row) => {
      const cells = columns
        .map((col) => {
          const val = cellValue(row, col);
          const type = /^-?\d+(\.\d+)?$/.test(val) ? 'Number' : 'String';
          return `<Cell><Data ss:Type="${type}">${xmlEscape(val)}</Data></Cell>`;
        })
        .join('');
      return `<Row>${cells}</Row>`;
    })
    .join('');

  const xml = `<?xml version="1.0"?>
<?mso-application progid="Excel.Sheet"?>
<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet"
 xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet">
 <Worksheet ss:Name="Export">
  <Table>
   <Row>${headerRow}</Row>
   ${dataRows}
  </Table>
 </Worksheet>
</Workbook>`;

  downloadBlob(xml, `${filename}.xls`, 'application/vnd.ms-excel');
}

function xmlEscape(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

export function downloadBlob(content: string, filename: string, mime: string): void {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

export async function downloadAuthenticatedExport(
  path: string,
  filename: string,
  token: string | null,
): Promise<void> {
  const res = await fetch(path, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) throw new Error('Export failed');
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}
