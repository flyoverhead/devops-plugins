default: fmt lint install generate

build:
	go build -v ./...

install: build
	go install -v ./...

fmt:
	gofmt -s -w -e .

lint:
	golangci-lint run

generate:
	go generate ./...

test:
	go test -v -cover -timeout=120s -parallel=10 ./...

testacc:
	TF_ACC=1 go test -v -cover -timeout 120m ./...

.PHONY: default build install fmt lint generate test testacc
