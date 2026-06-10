PLUGIN_NAME = processing_gflex
ZIP         = $(PLUGIN_NAME).zip

.PHONY: zip clean

zip:
	rm -f $(ZIP)
	zip -r $(ZIP) $(PLUGIN_NAME)/ \
		--exclude "$(PLUGIN_NAME)/__pycache__/*" \
		--exclude "$(PLUGIN_NAME)/algorithms/__pycache__/*"
	@echo "Created $(ZIP)"

clean:
	rm -f $(ZIP)
