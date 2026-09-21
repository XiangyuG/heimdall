PYTHON ?= python3
CASES := branch_expand helper_expand nest_expand branch_helper_nest \
	branch_helper_nest_basic slot_operations

.PHONY: help $(CASES)

help:
	@echo "Run a suite with:"
	@echo "  $(PYTHON) run_test.py --case <case>"
	@echo ""
	@echo "Available cases: $(CASES)"

$(CASES):
	$(PYTHON) run_test.py --case $@
