# AEOS Starter — roadmap vivo

Fuente normativa: [AEOS_STARTER_MVP_PLAN.md](AEOS_STARTER_MVP_PLAN.md). Issue: [#49](https://github.com/Franchute10/autonomous-agent-economy/issues/49). Plan PR: [#50](https://github.com/Franchute10/autonomous-agent-economy/pull/50).

**Corte:** 2026-11-24 (America/Lima).  
**Estado global:** PLANNING — dirección del producto preparada; checkpoint del propietario pendiente.  
**Fecha objetivo:** 2026-12-24, sujeta a los gates del plan.  
**Presupuesto autorizado:** USD 0 hasta aprobación expresa.

| ID | Semana | Entrega | Estado | Evidencia / salida |
|---|---:|---|---|---|
| S0-01 | 0 | Baseline GitHub, ramas y riesgos | DONE | AEOS main eaa8c525; LIVE de2d211b; motor main/ramas comparados; plan documenta divergencia |
| S0-02 | 0 | Alcance Starter y exclusiones | IN_REVIEW | Plan AEOS_STARTER_MVP_PLAN.md; issue #49; PR #50 |
| S0-03 | 0 | Confirmar primer departamento, despliegue, auth, DB y modelo | BLOCKED | Requiere checkpoint del propietario y spike técnico |
| S1-01 | 1 | Branch de implementación desde main e integración selectiva | TODO | No iniciar hasta aprobar alcance y revisar CI/PR |
| S1-02 | 1 | Auth, usuario, organización y membership | TODO | Registro/login y creación de tenant |
| S1-03 | 1 | Aislamiento multi-tenant PostgreSQL/RLS | TODO | Tests cross-tenant sobre PostgreSQL real |
| S1-04 | 1 | Perfil empresarial y documentos | TODO | CRUD y artefactos aislados por tenant |
| S1-05 | 1 | UI inicial desplegada | TODO | URL staging usable |
| S2-01 | 2 | Agent Registry Starter | TODO | Definiciones/versiones/capacidades/límites |
| S2-02 | 2 | Model Gateway (un proveedor) | TODO | Llamada real desde entorno controlado |
| S2-03 | 2 | Tool Gateway allowlisted | TODO | Schemas, autorización y auditoría |
| S2-04 | 2 | Runtime durable | TODO | Persistencia, lease, timeout, retry y recuperación |
| S2-05 | 2 | Orchestrator v1 | TODO | Instrucción → plan estructurado → ejecución autorizada |
| S2-06 | 2 | Centro de trabajo | TODO | Lista y detalle de tareas |
| S3-01 | 3 | Un workflow departamental completo | TODO | Recomendación: Comercial; confirmar |
| S3-02 | 3 | Evidencia y conocimiento | TODO | Fuentes y artefactos persistidos |
| S3-03 | 3 | Aprobaciones humanas | TODO | Aprobar/rechazar con auditoría |
| S3-04 | 3 | Historial y recuperación | TODO | Retomar sin duplicar efectos |
| S3-05 | 3 | Consumo y límites | TODO | Registro de uso y bloqueo por cuota |
| S4-01 | 4 | Hardening funcional | TODO | Seguridad, errores, idempotencia y permisos |
| S4-02 | 4 | E2E PostgreSQL en staging | TODO | Recorrido completo probado |
| S4-03 | 4 | Piloto cerrado en Perú | TODO | 2–3 usuarios/empresas; evaluación |
| S4-04 | 4 | Release Starter v0.1 | TODO | URL, guía, changelog y soporte |

## Cadencia de control
- Máximo dos tareas técnicas activas en paralelo.
- Cada hito DONE exige issue/PR, SHA, CI, pruebas con denominador y evidencia.
- BLOCKED más de medio día: documentar causa, alternativa y decisión requerida.
- Si el hito S2-05 no logra ejecución real desde UI al 11-12-2026, congelar ampliaciones y reducir alcance.
- Actualizar este archivo en cada cambio de estado; nunca marcar DONE por planificación o código sin validación.
