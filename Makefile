CXX ?= g++
CXXFLAGS ?= -std=c++17 -O2 -Wall -Wextra
BIN = eco

all: $(BIN)
$(BIN): src/main.cpp
	$(CXX) $(CXXFLAGS) -o $@ $<
test: $(BIN)
	sh tests/run_tests.sh
sanity: $(BIN)
	python3 tests/sanity.py
article:
	cd article && pdflatex -interaction=nonstopmode articulo.tex && pdflatex -interaction=nonstopmode articulo.tex
clean:
	rm -f $(BIN) article/*.aux article/*.log article/*.out article/pg-*.png
.PHONY: all test sanity article clean
