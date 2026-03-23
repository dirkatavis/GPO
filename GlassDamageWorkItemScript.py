# ...existing code...

def run_new_complaint_workitem_flow(driver, logger):
	"""
	Runs the end-to-end flow for creating a new complaint/work item using the implemented step functions.
	Args:
		driver: Selenium WebDriver instance
		logger: Logger instance
	"""
	try:
		logger.info("Starting new complaint/work item flow...")
		select_glass_repair_replace_opcode(driver, logger)
		click_create_work_item_button(driver, logger)
		click_final_done_button(driver, logger)
		logger.info("New complaint/work item flow completed successfully.")
	except Exception as e:
		logger.error(f"Error in new complaint/work item flow: {e}")
		raise
# ...existing code...

def click_final_done_button(driver, logger):
	"""
	Clicks the 'Done' button (final dialog) to complete the workflow.
	Args:
		driver: Selenium WebDriver instance
		logger: Logger instance
	"""
	from selenium.webdriver.common.by import By
	from selenium.webdriver.support.ui import WebDriverWait
	from selenium.webdriver.support import expected_conditions as EC
	try:
		logger.info("Clicking 'Done' button (final dialog)...")
		# Wait for the final dialog button to be present and enabled
		button_locator = (By.CLASS_NAME, "fleet-operations-pwa__finalDialogueButton__5dy90n")
		WebDriverWait(driver, 10).until(
			EC.element_to_be_clickable(button_locator)
		)
		button = driver.find_element(*button_locator)
		button.click()
		logger.info("'Done' button clicked.")
	except Exception as e:
		logger.error(f"Error clicking 'Done' button: {e}")
		raise
# ...existing code...

def click_create_work_item_button(driver, logger):
	"""
	Clicks the 'Create Work Item' button on the OpCodes screen.
	Args:
		driver: Selenium WebDriver instance
		logger: Logger instance
	"""
	from selenium.webdriver.common.by import By
	from selenium.webdriver.support.ui import WebDriverWait
	from selenium.webdriver.support import expected_conditions as EC
	try:
		logger.info("Clicking 'Create Work Item' button on OpCodes screen...")
		# Wait for the general container to be present
		container_locator = (By.CLASS_NAME, "fleet-operations-pwa__generalContainer__5dy90n")
		WebDriverWait(driver, 10).until(
			EC.presence_of_element_located(container_locator)
		)
		container = driver.find_element(*container_locator)
		# Find the enabled button inside the container
		button = container.find_element(By.XPATH, ".//button[not(contains(@class, 'bp6-disabled'))]")
		button.click()
		logger.info("'Create Work Item' button clicked.")
	except Exception as e:
		logger.error(f"Error clicking 'Create Work Item' button: {e}")
		raise
# (moved from project root)

def select_glass_repair_replace_opcode(driver, logger):
	"""
	Selects the 'Glass Repair/Replace' OpCode on the OpCodes screen.
	Args:
		driver: Selenium WebDriver instance
		logger: Logger instance
	"""
	from selenium.webdriver.common.by import By
	from selenium.webdriver.support.ui import WebDriverWait
	from selenium.webdriver.support import expected_conditions as EC
	try:
		logger.info("Selecting 'Glass Repair/Replace' OpCode...")
		# Wait for OpCode items to be present
		op_item_locator = (By.CLASS_NAME, "fleet-operations-pwa__opCodeItem__5dy90n")
		WebDriverWait(driver, 10).until(
			EC.presence_of_all_elements_located(op_item_locator)
		)
		op_items = driver.find_elements(*op_item_locator)
		found = False
		for item in op_items:
			try:
				# Find the text div inside the item
				text_div = item.find_element(By.CLASS_NAME, "fleet-operations-pwa__opCodeText__5dy90n")
				if text_div.text.strip() == "Glass Repair/Replace":
					item.click()
					logger.info("'Glass Repair/Replace' OpCode selected.")
					found = True
					break
			except Exception:
				continue
		if not found:
			logger.error("'Glass Repair/Replace' OpCode not found on the screen.")
			raise Exception("'Glass Repair/Replace' OpCode not found.")
	except Exception as e:
		logger.error(f"Error selecting 'Glass Repair/Replace' OpCode: {e}")
		raise
