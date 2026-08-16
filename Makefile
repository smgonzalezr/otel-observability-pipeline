.PHONY: local abajo carga benchmark figuras drawio reporte reporte-docx validar limpiar

local:            ## levanta el stack completo con docker compose
	docker compose up -d --build

abajo:
	docker compose down -v

carga:            ## genera trafico de ejemplo
	@for i in $$(seq 1 50); do \
	  curl -s -X POST localhost:8001/checkout -H 'Content-Type: application/json' \
	    -d '{"cliente_id":"cli-001","sku":"SKU-1001","cantidad":2,"precio_unitario":25000}' > /dev/null; \
	done; echo "50 peticiones enviadas"

benchmark:        ## corre el benchmark de la Fase 4
	python benchmark/run_benchmark.py --usuarios 50 --duracion 300 --repeticiones 3

figuras:          ## rehace las figuras 2 y 4 desde los datos medidos
	python scripts/generar_figuras.py

drawio:           ## regenera las figuras 1 y 3 en formato draw.io
	python scripts/generar_drawio.py

reporte:          ## reporte tecnico en PDF
	python scripts/generar_reporte.py

reporte-docx:     ## reporte tecnico en DOCX con normas APA 7
	npm install docx image-size --no-save
	node scripts/generar_reporte_docx.js

validar:          ## revisa la sintaxis de todo lo que se puede validar
	python -c "import yaml,glob,sys; [yaml.safe_load(open(f)) for f in glob.glob('collector/*.yaml')+glob.glob('dashboards/*.yml')+['docker-compose.yaml']]; print('YAML ok')"
	python -c "import json; json.load(open('dashboards/grafana-observabilidad.json')); print('dashboard ok')"
	python -m py_compile services/common/telemetry.py services/service-a/app.py services/service-b/app.py && echo "Python ok"
	cd iac/terraform/gcp && terraform fmt -check && terraform validate || true
	cd iac/terraform/aws && terraform fmt -check && terraform validate || true

limpiar:
	rm -rf __pycache__ */__pycache__ *.db /tmp/service_*.db
