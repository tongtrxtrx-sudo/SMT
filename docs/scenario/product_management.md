# Product management and operator attribution scenarios

## Current operator

**Given** the application has started without an operator  
**When** a user tries to import a BOM, change master data, or start a production run  
**Then** the write is rejected with a prompt to enter the current operator.

**Given** operator `OP-01` is confirmed  
**When** that operator imports a BOM and configuration and starts a run  
**Then** the BOM provenance, configuration creator, run header, and audit events record `OP-01`.

## Master data lifecycle

**Given** devices and stations exist  
**When** a manager filters, updates non-identity fields, disables, or re-enables them  
**Then** the tables refresh with enabled, disabled, referenced, and archived state shown separately.

**Given** a station has never been referenced  
**When** it is deleted  
**Then** it is removed and the deletion is audited.

**Given** a station is referenced by a configuration or production snapshot  
**When** it is retired  
**Then** deletion is protected and the manager archives it instead.

## BOM and configuration versions

**Given** two BOM versions for one product  
**When** they are compared  
**Then** added, removed, and changed material codes are displayed with immutable source provenance.

**Given** a BOM or configuration has been published  
**When** another change is required  
**Then** the operator imports an explicit new BOM version or copies the configuration into a new
draft; released details are not edited in place.

**Given** a configuration draft  
**When** assignments are edited, validated, published, and activated  
**Then** only that active non-empty version is available to scanning while all referenced master
data remains enabled.

## Production runs and audit query

**Given** a run starts before any scans  
**When** the application closes, the operator changes, or another run starts  
**Then** the zero-scan or unfinished run is persisted as interrupted with its snapshot and reason.

**Given** an interrupted run  
**When** a current operator resumes it from production-run management  
**Then** completed station progress and previous attempts are restored on the scan page, and later
run actions use the resuming operator.

**Given** append-only scan attempts and audit entries  
**When** audit history is filtered by entity, operator, action, or ISO time range  
**Then** matching entries are shown newest first and no edit or delete action is available.
