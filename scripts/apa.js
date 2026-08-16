/**
 * Piezas de formato APA 7 para armar el reporte en DOCX.
 *
 * Times New Roman 12, interlineado doble, margenes de una pulgada,
 * numero de pagina arriba a la derecha, tablas sin lineas verticales y
 * referencias con sangria francesa.
 */

const d = require('docx');
const {
  Paragraph, TextRun, HeadingLevel, AlignmentType, Table, TableRow, TableCell,
  WidthType, BorderStyle, ShadingType,
} = d;

const FUENTE = 'Times New Roman';
const MONO = 'Consolas';
const DOBLE = { line: 480, before: 0, after: 0 };

const SIN = { style: BorderStyle.NONE, size: 0, color: 'FFFFFF' };
const LINEA = { style: BorderStyle.SINGLE, size: 6, color: '000000' };

// Interpreta **negrita**, *cursiva* y `codigo` dentro de un texto plano.
function trozos(texto, tam = 24) {
  const salida = [];
  const re = /(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`)/g;
  let ultimo = 0, m;
  while ((m = re.exec(texto)) !== null) {
    if (m.index > ultimo) {
      salida.push(new TextRun({ text: texto.slice(ultimo, m.index), font: FUENTE, size: tam }));
    }
    const t = m[0];
    if (t.startsWith('**')) {
      salida.push(new TextRun({ text: t.slice(2, -2), font: FUENTE, size: tam, bold: true }));
    } else if (t.startsWith('`')) {
      salida.push(new TextRun({ text: t.slice(1, -1), font: MONO, size: tam - 3 }));
    } else {
      salida.push(new TextRun({ text: t.slice(1, -1), font: FUENTE, size: tam, italics: true }));
    }
    ultimo = m.index + t.length;
  }
  if (ultimo < texto.length) {
    salida.push(new TextRun({ text: texto.slice(ultimo), font: FUENTE, size: tam }));
  }
  return salida;
}

// Parrafo de cuerpo, doble espacio y sangria de primera linea de media pulgada.
function p(texto, opciones = {}) {
  return new Paragraph({
    spacing: DOBLE,
    indent: opciones.sinSangria ? undefined : { firstLine: 720 },
    alignment: AlignmentType.LEFT,
    children: trozos(texto),
  });
}

// Nivel 1: centrado y en negrita.
function h1(texto) {
  return new Paragraph({
    spacing: DOBLE,
    alignment: AlignmentType.CENTER,
    heading: HeadingLevel.HEADING_1,
    children: [new TextRun({ text: texto, font: FUENTE, size: 24, bold: true, color: '000000' })],
  });
}

// Nivel 2: al margen y en negrita.
function h2(texto) {
  return new Paragraph({
    spacing: DOBLE,
    heading: HeadingLevel.HEADING_2,
    children: [new TextRun({ text: texto, font: FUENTE, size: 24, bold: true, color: '000000' })],
  });
}

// Nivel 3: al margen, negrita y cursiva.
function h3(texto) {
  return new Paragraph({
    spacing: DOBLE,
    heading: HeadingLevel.HEADING_3,
    children: [new TextRun({ text: texto, font: FUENTE, size: 24, bold: true, italics: true, color: '000000' })],
  });
}

function vineta(texto, nivel = 0) {
  return new Paragraph({
    spacing: DOBLE,
    numbering: { reference: 'vinetas', level: nivel },
    children: trozos(texto),
  });
}

function vacio() {
  return new Paragraph({ spacing: DOBLE, children: [new TextRun({ text: '', font: FUENTE, size: 24 })] });
}

// Bloque de codigo o de salida literal, a un espacio y en fuente monoespaciada.
function codigo(lineas) {
  return lineas.split('\n').map((l) => new Paragraph({
    spacing: { line: 220, before: 0, after: 0 },
    shading: { type: ShadingType.CLEAR, fill: 'F4F4F4' },
    children: [new TextRun({ text: l === '' ? ' ' : l, font: MONO, size: 18 })],
  }));
}

// --- rotulos de tablas y figuras -------------------------------------------

function numeroTabla(texto) {
  return new Paragraph({
    spacing: { line: 480, before: 240, after: 0 },
    children: [new TextRun({ text: texto, font: FUENTE, size: 24, bold: true })],
  });
}

function tituloTabla(texto) {
  return new Paragraph({
    spacing: { line: 480, before: 0, after: 120 },
    children: [new TextRun({ text: texto, font: FUENTE, size: 24, italics: true })],
  });
}

function nota(texto) {
  return new Paragraph({
    spacing: { line: 240, before: 120, after: 240 },
    children: [
      new TextRun({ text: 'Nota. ', font: FUENTE, size: 20, italics: true }),
      ...trozos(texto, 20),
    ],
  });
}


function celda(texto, { negrita = false, centrado = false, mono = false } = {}) {
  return new Paragraph({
    spacing: { line: 240, before: 40, after: 40 },
    alignment: centrado ? AlignmentType.CENTER : AlignmentType.LEFT,
    children: [new TextRun({
      text: texto,
      font: mono ? MONO : FUENTE,
      size: mono ? 17 : 20,
      bold: negrita,
    })],
  });
}

/**
 * Tabla en formato APA: linea arriba, linea bajo el encabezado, linea al final
 * y ninguna linea vertical.
 */
function tablaApa(encabezado, filas, anchos, opciones = {}) {
  const total = anchos.reduce((a, b) => a + b, 0);
  const monoCols = opciones.monoCols || [];
  const centrar = opciones.centrar || [];

  const filaEncabezado = new TableRow({
    tableHeader: true,
    children: encabezado.map((t, i) => new TableCell({
      width: { size: anchos[i], type: WidthType.DXA },
      borders: { top: LINEA, bottom: LINEA, left: SIN, right: SIN },
      children: [celda(t, { negrita: true, centrado: i > 0 })],
    })),
  });

  const cuerpo = filas.map((fila, ri) => new TableRow({
    children: fila.map((t, i) => new TableCell({
      width: { size: anchos[i], type: WidthType.DXA },
      borders: {
        top: SIN,
        bottom: ri === filas.length - 1 ? LINEA : SIN,
        left: SIN,
        right: SIN,
      },
      children: [celda(t, {
        centrado: centrar.includes(i),
        mono: monoCols.includes(i),
      })],
    })),
  }));

  return new Table({
    columnWidths: anchos,
    width: { size: total, type: WidthType.DXA },
    rows: [filaEncabezado, ...cuerpo],
  });
}

// Referencia con sangria francesa de media pulgada.
function referencia(texto) {
  return new Paragraph({
    spacing: DOBLE,
    indent: { left: 720, hanging: 720 },
    children: trozos(texto),
  });
}

module.exports = {
  d, FUENTE, MONO, DOBLE, SIN, LINEA,
  p, h1, h2, h3, vineta, vacio, codigo,
  numeroTabla, tituloTabla, nota, tablaApa, referencia, celda, trozos,
};
