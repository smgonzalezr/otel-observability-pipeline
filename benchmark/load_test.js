// =============================================================================
// Prueba de carga con k6 para la Fase 4.
//
// Corre el mismo escenario dos veces, una con los servicios sin instrumentar y
// otra con OTel activo, y compara los resultados.
//
//   k6 run -e ESCENARIO=sin_otel load_test.js
//   k6 run -e ESCENARIO=con_otel load_test.js
//
// La carga sigue la recomendacion de la actividad: 50 usuarios concurrentes
// durante 5 minutos, con rampa de subida y de bajada.
// =============================================================================

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Trend, Rate, Counter } from 'k6/metrics';

const BASE = __ENV.BASE_URL || 'http://localhost:8001';
const ESCENARIO = __ENV.ESCENARIO || 'sin_otel';
const USUARIOS = parseInt(__ENV.USUARIOS || '50');

// Metricas propias para poder comparar las dos corridas.
const duracionCheckout = new Trend('checkout_duracion_ms', true);
const tasaExito = new Rate('checkout_exito');
const pedidosOk = new Counter('pedidos_confirmados');
const conTraceId = new Rate('respuestas_con_trace_id');

export const options = {
  scenarios: {
    carga: {
      executor: 'ramping-vus',
      startVUs: 0,
      stages: [
        { duration: '30s', target: USUARIOS },  // subida
        { duration: '5m', target: USUARIOS },   // meseta, es la que se mide
        { duration: '30s', target: 0 },         // bajada
      ],
      gracefulRampDown: '15s',
    },
  },
  // El calentamiento no debe contaminar la comparacion.
  thresholds: {
    'http_req_duration{escenario:medicion}': ['p(95)<1500', 'p(99)<3000'],
    checkout_exito: ['rate>0.99'],
    http_req_failed: ['rate<0.01'],
  },
  summaryTrendStats: ['avg', 'min', 'med', 'p(90)', 'p(95)', 'p(99)', 'max'],
  tags: { escenario: ESCENARIO },
};

const SKUS = Array.from({ length: 50 }, (_, i) => `SKU-${1000 + i}`);
const CLIENTES = Array.from({ length: 60 }, (_, i) => `cli-${String(i).padStart(3, '0')}`);

function aleatorio(lista) {
  return lista[Math.floor(Math.random() * lista.length)];
}

export default function () {
  const cuerpo = JSON.stringify({
    cliente_id: aleatorio(CLIENTES),
    sku: aleatorio(SKUS),
    cantidad: Math.floor(Math.random() * 3) + 1,
    precio_unitario: 15000 + Math.floor(Math.random() * 20) * 1000,
  });

  const res = http.post(`${BASE}/checkout`, cuerpo, {
    headers: { 'Content-Type': 'application/json' },
    tags: { escenario: 'medicion', endpoint: 'checkout' },
  });

  const ok = check(res, {
    'codigo 200': (r) => r.status === 200,
    'trae pedido_id': (r) => {
      try {
        return typeof r.json('pedido_id') === 'string';
      } catch (e) {
        return false;
      }
    },
  });

  duracionCheckout.add(res.timings.duration);
  tasaExito.add(ok);

  if (ok) {
    pedidosOk.add(1);
    // En la corrida con OTel la respuesta trae el trace_id. Sirve para
    // comprobar que la propagacion de contexto quedo activa.
    try {
      const tid = res.json('trace_id');
      conTraceId.add(Boolean(tid && tid.length === 32));
    } catch (e) {
      conTraceId.add(false);
    }
  }

  sleep(0.1);
}

export function handleSummary(data) {
  const m = data.metrics;
  const resumen = {
    escenario: ESCENARIO,
    usuarios: USUARIOS,
    peticiones: m.http_reqs ? m.http_reqs.values.count : 0,
    rps: m.http_reqs ? Number(m.http_reqs.values.rate.toFixed(1)) : 0,
    latencia_ms: {
      media: Number(m.http_req_duration.values.avg.toFixed(2)),
      p50: Number(m.http_req_duration.values.med.toFixed(2)),
      p95: Number(m.http_req_duration.values['p(95)'].toFixed(2)),
      p99: Number(m.http_req_duration.values['p(99)'].toFixed(2)),
      max: Number(m.http_req_duration.values.max.toFixed(2)),
    },
    tasa_error: Number((m.http_req_failed.values.rate * 100).toFixed(3)),
    pedidos_confirmados: m.pedidos_confirmados ? m.pedidos_confirmados.values.count : 0,
    respuestas_con_trace_id: m.respuestas_con_trace_id
      ? Number((m.respuestas_con_trace_id.values.rate * 100).toFixed(1))
      : 0,
  };

  return {
    stdout: '\n' + JSON.stringify(resumen, null, 2) + '\n',
    [`results/k6_${ESCENARIO}.json`]: JSON.stringify(resumen, null, 2),
  };
}
