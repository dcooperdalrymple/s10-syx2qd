BUILD_DIR = ./bin
TEST_DIR = ./example-files
SRC_DIR = ./src

PACKAGE = s10-syx2qd
OBJ = $(BUILD_DIR)/$(PACKAGE)
SRCS = $(SRC_DIR)/main.c $(SRC_DIR)/global.c $(SRC_DIR)/syx.c $(SRC_DIR)/qd.c

all: clean dir compile test
build: dir compile

dir:
	mkdir $(BUILD_DIR)

compile:
	gcc $(SRCS) -o $(OBJ) -Wall

test:
	@- find "$(TEST_DIR)" -type f -name "*.syx" | while read fname; do \
		echo "Processing: $$fname" ; \
		$(OBJ) "$$fname" ; \
	done

clean:
	rm -r $(BUILD_DIR) || true
	rm $(TEST_DIR)/*.qd || true
