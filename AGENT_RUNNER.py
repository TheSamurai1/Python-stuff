import argparse
import asyncio
import json
import logging
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from browser_use import (
    Agent,
    Browser,
    ChatAnthropic,
    ChatAzureOpenAI,
    ChatGoogle,
    ChatGroq,
    ChatOllama,
    ChatOpenAI,
)
from dotenv import load_dotenv
from pydantic import SecretStr

logger = logging.getLogger(__name__)

load_dotenv()

SYSTEM_PROMPT = """
You are a deterministic web automation agent.
- Follow the provided task exactly.
- Prefer XPath selectors when available; otherwise use stable CSS.
- Never guess or click ambiguous elements.
- Be resilient to slow loads (wait for 'load' and use timeouts).
"""



@dataclass
class TestResult:
    """Represents the result of a single test variation."""
    variation_id: str
    success: bool
    script_path: Optional[str] = None
    error_message: Optional[str] = None
    execution_time: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class DynamicTestRunner:
    """Handles running tests with multiple variations and dynamic data injection."""
    
    def __init__(self, base_task_template: str, llm, max_steps: int = 100, output_dir: Optional[str] = None, variables_file_path: Optional[str] = None, generate_script: bool = True):
        self.base_task_template = base_task_template
        self.llm = llm
        self.max_steps = max_steps
        self.output_dir = output_dir
        self.variables_file_path = variables_file_path
        self.generate_script = generate_script
        self.results: List[TestResult] = []
    
    def inject_data_into_template(self, template: str, variation_data: Dict[str, Any]) -> str:
        """Inject dynamic data into the task template."""
        modified_task = template
        
        # Replace placeholders in the template
        for key, value in variation_data.items():
            placeholder = f"{{{key}}}"
            if placeholder in modified_task:
                modified_task = modified_task.replace(placeholder, str(value))
        
        return modified_task
    
    async def run_single_variation(self, variation_id: str, variation_data: Dict[str, Any]) -> TestResult:
        """Run a single test variation."""
        start_time = datetime.now()
        result = TestResult(variation_id=variation_id, success=False)
        
        try:
            # Inject data into template
            task = self.inject_data_into_template(self.base_task_template, variation_data)
            
            # Run the agent with the modified task
            script_content = await main(task, self.llm, self.max_steps, output_dir=self.output_dir, variables_file_path=self.variables_file_path, generate_script=self.generate_script)
            
            # Extract script path from the generated content
            script_path = self._extract_script_path(script_content)
            
            result.success = True
            result.script_path = script_path
            result.metadata = {
                "task": task,
                "variation_data": variation_data
            }
            
        except Exception as e:
            result.error_message = str(e)
            logger.error(f"Error running variation {variation_id}: {e}")
        
        finally:
            end_time = datetime.now()
            result.execution_time = (end_time - start_time).total_seconds()
        
        return result
    
    def _extract_script_path(self, script_content: str) -> Optional[str]:
        """Extract the script path from the generated content."""
        lines = script_content.split('\n')
        for line in lines:
            if 'Generated Playwright script saved to:' in line:
                return line.split(': ')[-1].strip()
        return None
    
    async def run_parallel_variations(self, variations: List[Dict[str, Any]], max_concurrent: int = 3) -> List[TestResult]:
        """Run multiple test variations in parallel."""
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def run_with_semaphore(variation):
            variation_id = variation.get("variation_id", f"variation_{variations.index(variation)}")
            variation_data = {k: v for k, v in variation.items() if k != "variation_id"}
            
            async with semaphore:
                return await self.run_single_variation(variation_id, variation_data)
        
        tasks = [run_with_semaphore(variation) for variation in variations]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Handle any exceptions that occurred
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                variation_id = variations[i].get("variation_id", f"variation_{i}")
                processed_results.append(TestResult(
                    variation_id=variation_id,
                    success=False,
                    error_message=str(result)
                ))
            else:
                processed_results.append(result)
        
        self.results.extend(processed_results)
        return processed_results
    
    async def run_sequential_variations(self, variations: List[Dict[str, Any]]) -> List[TestResult]:
        """Run multiple test variations sequentially."""
        results = []
        for variation in variations:
            variation_id = variation.get("variation_id", f"variation_{variations.index(variation)}")
            variation_data = {k: v for k, v in variation.items() if k != "variation_id"}
            result = await self.run_single_variation(variation_id, variation_data)
            results.append(result)
        
        self.results.extend(results)
        return results
    
    def generate_summary_report(self) -> str:
        """Generate a summary report of all test results."""
        if not self.results:
            return "No test results available."
        
        total_tests = len(self.results)
        successful_tests = sum(1 for r in self.results if r.success)
        failed_tests = total_tests - successful_tests
        
        report = f"""
=== Test Execution Summary ===
Total Tests: {total_tests}
Successful: {successful_tests}
Failed: {failed_tests}
Success Rate: {(successful_tests/total_tests)*100:.1f}%

=== Detailed Results ===
"""
        
        for result in self.results:
            status = "✅ PASS" if result.success else "❌ FAIL"
            report += f"\n{status} - {result.variation_id}"
            if result.execution_time:
                report += f" (Execution time: {result.execution_time:.2f}s)"
            if result.error_message:
                report += f"\n  Error: {result.error_message}"
            if result.script_path:
                report += f"\n  Script: {result.script_path}"
        
        return report
    
    def save_results_to_file(self, filename: Optional[str] = None) -> str:
        """Save test results to a JSON file."""
        if not filename:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"test_results_{timestamp}.json"
        
        results_data = []
        for result in self.results:
            results_data.append({
                "variation_id": result.variation_id,
                "success": result.success,
                "script_path": result.script_path,
                "error_message": result.error_message,
                "execution_time": result.execution_time,
                "metadata": result.metadata
            })
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(results_data, f, indent=2, ensure_ascii=False)
        
        return filename


class PlaywrightScriptGenerator:
	"""Generates a Playwright script from AgentHistoryList."""

	def __init__(
		self,
		history_list: list[dict[str, Any]],
		sensitive_data_keys: list[str] | None = None,
		variables_file_path: str | None = None,
		# browser_config: BrowserConfig | None = None,
		# context_config: BrowserContextConfig | None = None,
	):
		"""
		Initializes the script generator.

		Args:
		    history_list: A list of dictionaries, where each dictionary represents an AgentHistory item.
		                 Expected to be raw dictionaries from `AgentHistoryList.model_dump()`.
		    sensitive_data_keys: A list of keys used as placeholders for sensitive data.
		    variables_file_path: Path to JSON file containing sensitive data variables.
		    browser_config: Configuration from the original Browser instance.
		    context_config: Configuration from the original BrowserContext instance.
		"""
		self.history = history_list
		# print(type(self.history), "the history")
		self.sensitive_data_keys = sensitive_data_keys or []
		self.variables_file_path = variables_file_path
		self.browser_config = {'headless': False}
		# self.context_config = context_config
		self._imports_helpers_added = False
		self._page_counter = 0  # Track pages for tab management

		# Dictionary mapping action types to handler methods
		self._action_handlers = {
			'go_to_url': self._map_go_to_url,
			'wait': self._map_wait,
			'input_text': self._map_input_text,
			'click_element': self._map_click_element,
			'click_element_by_index': self._map_click_element,  # Map legacy action
			'scroll_down': self._map_scroll_down,
			'scroll_up': self._map_scroll_up,
			'scroll': self._map_scroll_down,  # Map generic scroll to scroll_down
			'send_keys': self._map_send_keys,
			'go_back': self._map_go_back,
			'open_tab': self._map_open_tab,
			'close_tab': self._map_close_tab,
			'switch_tab': self._map_switch_tab,
			'search_google': self._map_search_google,
			'drag_drop': self._map_drag_drop,
			'extract_content': self._map_extract_content,
			'click_download_button': self._map_click_download_button,
			'done': self._map_done,
		}

	def _convert_sensitive_value_to_placeholder(self, text: str, selector: str = None) -> str:
		"""
		Convert actual sensitive values to placeholders that can be replaced from JSON.
		
		Args:
			text: The text value that might contain sensitive data
			selector: Optional selector string to help identify the input type
			
		Returns:
			Placeholder string like {username}, {password}, {website} if detected,
			otherwise returns the original text
		"""
		text_str = str(text).strip()
		selector_lower = (selector or '').lower()
		
		# Check selector context first (most reliable)
		if 'password' in selector_lower or 'input[type="password"]' in selector_lower:
			if 'password' in self.sensitive_data_keys:
				return '{password}'
		elif 'email' in selector_lower or 'input[type="email"]' in selector_lower or '@' in text_str:
			if 'username' in self.sensitive_data_keys:
				return '{username}'
		elif 'url' in selector_lower or 'website' in selector_lower or 'http' in text_str.lower():
			if 'website' in self.sensitive_data_keys:
				return '{website}'
		
		# Fallback: Check each sensitive data key and try to match patterns
		for key in self.sensitive_data_keys:
			# For username, check if it looks like an email
			if key == 'username' and ('@' in text_str and '.' in text_str):
				return f'{{{key}}}'
			# For password, check if it's a complex string (has special chars, numbers, etc.)
			elif key == 'password' and len(text_str) > 6 and any(c in text_str for c in ['#', '@', '!', '$', '%', '&', '*', '0', '1', '2', '3', '4', '5', '6', '7', '8', '9']):
				return f'{{{key}}}'
			# For website, check if it looks like a URL
			elif key == 'website' and ('http' in text_str.lower() or text_str.startswith('www.') or '.com' in text_str.lower() or '.net' in text_str.lower() or '.org' in text_str.lower()):
				return f'{{{key}}}'
		
		# If no match, return the text as-is (will be wrapped in replace_sensitive_data)
		return text_str

	def _generate_browser_launch_args(self) -> str:
		"""Generates the arguments string for browser launch based on BrowserConfig."""
		if not self.browser_config:
			# Default launch if no config provided
			return 'headless=False'

		# Handle dictionary format browser config
		if isinstance(self.browser_config, dict):
			args_dict = self.browser_config.copy()
			print(f"Browser config: {args_dict}", "the if statement")
		else:
			# Handle object format browser config (legacy)
			args_dict = {
				'headless': getattr(self.browser_config, 'headless', False),
			}
			if hasattr(self.browser_config, 'proxy') and self.browser_config.proxy:
				args_dict['proxy'] = self.browser_config.proxy.model_dump() if hasattr(self.browser_config.proxy, 'model_dump') else self.browser_config.proxy
				print("Browser config: the else statement")

		# Filter out None values
		args_dict = {k: v for k, v in args_dict.items() if v is not None}

		# Format as keyword arguments string
		args_str = ', '.join(f'{key}={repr(value)}' for key, value in args_dict.items())
		return args_str


	def _get_imports_and_helpers(self) -> list[str]:
		"""Generates necessary import statements (excluding helper functions)."""
		# Return only the standard imports needed by the main script body
		return [
			'import asyncio',
			'import json',
			'import os',
			'import sys',
			'from pathlib import Path',  # Added Path import
			'import urllib.parse',  # Needed for search_google
			'from playwright.async_api import async_playwright, Page, BrowserContext',  # Added BrowserContext
			'from dotenv import load_dotenv',
			'',
			'# Load environment variables',
			'load_dotenv(override=True)',
			'',
			# Helper function definitions are no longer here
		]

	def _get_sensitive_data_definitions(self) -> list[str]:
		"""Generates the SENSITIVE_DATA dictionary definition using JSON file loading."""
		# Build environment variable mapping for get_sensitive_data
		env_vars_dict = {}
		if self.sensitive_data_keys:
			for key in self.sensitive_data_keys:
				env_vars_dict[key] = key.upper()
		
		# Use provided variables file path or default to "sensitive_data.json"
		# If a path is provided, preserve it (absolute stays absolute, relative stays relative)
		# This allows the generated script to work from any directory
		if self.variables_file_path:
			# Expand user directory (~) if present
			expanded_path = os.path.expanduser(self.variables_file_path)
			variables_path_obj = Path(expanded_path)
			
			# If it's already absolute, resolve it (handles symlinks, etc.)
			if variables_path_obj.is_absolute():
				if variables_path_obj.exists():
					variables_path = str(variables_path_obj.resolve())
				else:
					variables_path = str(variables_path_obj)
			else:
				# Keep relative paths as-is so they work from the script's directory
				variables_path = expanded_path
		else:
			variables_path = "sensitive_data.json"
		
		# Escape the path for use in Python string
		variables_path_escaped = json.dumps(variables_path)
		
		# Store env_vars_dict for use in command-line argument handling
		env_vars_str = json.dumps(env_vars_dict, indent=4) if env_vars_dict else "None"
		
		lines = [
			f'# Sensitive data loaded from JSON file ({variables_path}) with fallback to environment variables',
			'# The helper functions (get_sensitive_data) are loaded above',
			f'# Default variables file path and env vars mapping (can be overridden with --variables)',
			f'_DEFAULT_VARIABLES_PATH = {variables_path_escaped}',
			f'_ENV_VARS_MAPPING = {env_vars_str}',
			'# SENSITIVE_DATA will be initialized after parsing command-line arguments in __main__ block',
			'# Initialize as empty dict at module level (will be populated in __main__)',
			'SENSITIVE_DATA = {}',
		]
		
		lines.append('')
		return lines

	def _get_selector_for_action(self, history_item: dict, action_index_in_step: int) -> str | None:
		"""
		Gets the selector (preferring XPath) for a given action index within a history step.
		Formats the XPath correctly for Playwright.
		"""

		state = history_item.get('state')
		if not isinstance(state, dict):
			logger.debug(f'State is not a dictionary: {type(state)}')
			return None
		interacted_elements = state.get('interacted_element')
		if not isinstance(interacted_elements, list):
			logger.debug(f'Interacted elements is not a list: {type(interacted_elements)}')
			return None
		if action_index_in_step >= len(interacted_elements):
			logger.debug(f'Action index {action_index_in_step} >= length of interacted_elements {len(interacted_elements)}')
			return None
		element_data = interacted_elements[action_index_in_step]
		if not isinstance(element_data, dict):
			logger.debug(f'Element data is not a dictionary: {type(element_data)}')
			return None
		
		# Prioritize XPath - check both 'xpath' and 'x_path' keys
		xpath = element_data.get('xpath') or element_data.get('x_path')
		if isinstance(xpath, str) and xpath.strip():
			# If xpath doesn't start with xpath=, /, or //, add the xpath= prefix and make it absolute
			if not xpath.startswith('xpath=') and not xpath.startswith('/') and not xpath.startswith('//'):
				xpath_selector = f'xpath=//{xpath}'  # Make relative if not already
			elif not xpath.startswith('xpath='):
				xpath_selector = f'xpath={xpath}'  # Add prefix if missing
			else:
				xpath_selector = xpath
			logger.debug(f'Found XPath selector: {xpath_selector}')
			return xpath_selector

		# Fallback to CSS selector if XPath is missing
		css_selector = element_data.get('css_selector')
		if isinstance(css_selector, str) and css_selector.strip():
			logger.debug(f'Found CSS selector: {css_selector}')
			return css_selector  # Use CSS selector as is

		# Try to find any other selector types
		for selector_key in ['selector', 'locator', 'element_selector']:
			selector = element_data.get(selector_key)
			if isinstance(selector, str) and selector.strip():
				logger.debug(f'Found {selector_key} selector: {selector}')
				return selector

		logger.warning(
			f'Could not find a usable XPath or CSS selector for action index {action_index_in_step} (element index {element_data.get("highlight_index", "N/A")}). Available keys: {list(element_data.keys())}'
		)
		return None

	def _get_goto_timeout(self) -> int:
		"""Gets the page navigation timeout in milliseconds."""
		default_timeout = 90000  # Default 90 seconds
		# if self.context_config and self.context_config.maximum_wait_page_load_time:
		# 	# Convert seconds to milliseconds
		# 	return int(self.context_config.maximum_wait_page_load_time * 1000)
		return default_timeout

	# --- Action Mapping Methods ---
	def _map_go_to_url(self, params: dict, step_info_str: str, **kwargs) -> list[str]:
		url = params.get('url')
		goto_timeout = self._get_goto_timeout()
		script_lines = []
		if url and isinstance(url, str):
			escaped_url = json.dumps(url)
			script_lines.append(f'            print(f"Navigating to: {url} ({step_info_str})")')
			script_lines.append(f'            await page.goto({escaped_url}, timeout={goto_timeout}, wait_until="domcontentloaded")')
			# Removed wait_for_load_state for faster execution - goto already waits
		else:
			script_lines.append(f'            # Skipping go_to_url ({step_info_str}): missing or invalid url')
		return script_lines

	def _map_wait(self, params: dict, step_info_str: str, **kwargs) -> list[str]:
		seconds = params.get('seconds', 0)  # Default to 0 for faster execution
		try:
			wait_seconds = int(seconds)
			if wait_seconds < 0:
				wait_seconds = 0
		except (ValueError, TypeError):
			wait_seconds = 0  # Default to 0 for faster execution
		if wait_seconds > 0:
			return [
				f'            print(f"Waiting for {wait_seconds} seconds... ({step_info_str})")',
				f'            await asyncio.sleep({wait_seconds})',
			]
		else:
			return [
				f'            # Skipping wait ({step_info_str}) - set to 0 for faster execution',
			]

	def _map_input_text(
		self, params: dict, history_item: dict, action_index_in_step: int, step_info_str: str, **kwargs
	) -> list[str]:
		index = params.get('index')
		text = params.get('text', '')
		selector = self._get_selector_for_action(history_item, action_index_in_step)
		script_lines = []
		
		# Convert sensitive values to placeholders (pass selector for better detection)
		placeholder_text = self._convert_sensitive_value_to_placeholder(text, selector)
		
		if selector and index is not None:
			clean_text_expression = f'replace_sensitive_data({json.dumps(placeholder_text)}, SENSITIVE_DATA)'
			escaped_selector = json.dumps(selector)
			escaped_step_info = json.dumps(step_info_str)
			# Check if this is a number input or single character (needs special handling)
			is_number_or_single_char = str(text).isdigit() or len(str(text)) == 1
			script_lines.append(
				f'            await _try_locate_and_act(page, {escaped_selector}, "fill", text={clean_text_expression}, step_info={escaped_step_info})'
			)
			# Add small delay after number/single char inputs for better reliability
			if is_number_or_single_char:
				script_lines.append('            await page.wait_for_timeout(200)  # Small delay for number input')
		else:
			# Try to use a generic input selector as fallback
			script_lines.append(f'            # Attempting input_text with generic selector ({step_info_str})')
			script_lines.append(f'            try:')
			script_lines.append(f'                # Try common input selectors')
			script_lines.append(f'                input_selectors = [')
			script_lines.append(f'                    "input[type=\\"number\\"]",')
			script_lines.append(f'                    "input[type=\\"tel\\"]",')
			script_lines.append(f'                    "input[type=\\"text\\"]",')
			script_lines.append(f'                    "input[type=\\"email\\"]",')
			script_lines.append(f'                    "input[type=\\"password\\"]",')
			script_lines.append(f'                    "input[data-testid]",')
			script_lines.append(f'                    "input[aria-label]",')
			script_lines.append(f'                    "input[placeholder]",')
			script_lines.append(f'                ]')  # Removed "input:not([type])" - too generic
			script_lines.append(f'                for selector in input_selectors:')
			script_lines.append(f'                    try:')
			clean_text_expression = f'replace_sensitive_data({json.dumps(placeholder_text)}, SENSITIVE_DATA)'
			script_lines.append(f'                        await _try_locate_and_act(page, selector, "fill", text={clean_text_expression}, step_info={json.dumps(step_info_str)})')
			script_lines.append(f'                        break')
			script_lines.append(f'                    except:')
			script_lines.append(f'                        continue')
			script_lines.append(f'            except Exception as e:')
			script_lines.append(f'                print(f"  Warning: Could not input text ({step_info_str}): {{e}}", file=sys.stderr)')
		return script_lines

	def _map_click_element(
		self, params: dict, history_item: dict, action_index_in_step: int, step_info_str: str, action_type: str, **kwargs
	) -> list[str]:
		if action_type == 'click_element_by_index':
			logger.warning(f"Mapping legacy 'click_element_by_index' to 'click_element' ({step_info_str})")
		index = params.get('index')
		selector = self._get_selector_for_action(history_item, action_index_in_step)
		script_lines = []
		
		if selector and index is not None:
			escaped_selector = json.dumps(selector)
			escaped_step_info = json.dumps(step_info_str)
			# Add a wait after clicking to allow page transitions
			script_lines.append(
				f'            await _try_locate_and_act(page, {escaped_selector}, "click", step_info={escaped_step_info})'
			)
			# Removed unnecessary wait_for_timeout(2000) - no longer needed
		elif "continue" in step_info_str.lower() or "submit" in step_info_str.lower():
			# Special handling for Continue/Submit buttons
			script_lines.append(f'            # Special handling for Continue/Submit button ({step_info_str})')
			script_lines.append(f'            try:')
			script_lines.append(f'                # Try form submission approaches')
			script_lines.append(f'                submit_selectors = [')
			script_lines.append(f'                    "button[type=\\"submit\\"]",')
			script_lines.append(f'                    "input[type=\\"submit\\"]",')
			# script_lines.append(f'                    "button:contains(\\"Continue\\")",')  # Commented out - not working reliably
			# script_lines.append(f'                    "button:contains(\\"Submit\\")",')  # Commented out - not working reliably
			# script_lines.append(f'                    "button:contains(\\"Next\\")",')  # Commented out - not working reliably
			script_lines.append(f'                    "button:not([disabled])",')
			# script_lines.append(f'                    "button"')  # Commented out - too generic, causes issues
			script_lines.append(f'                ]')
		else:
			# Try to use generic button/clickable selectors as fallback
			script_lines.append(f'            # Attempting {action_type} with generic selector ({step_info_str})')
			script_lines.append(f'            try:')
			script_lines.append(f'                # Try common clickable selectors in order of preference')
			script_lines.append(f'                click_selectors = [')
			script_lines.append(f'                    "button[type=\\"submit\\"]",')
			script_lines.append(f'                    "input[type=\\"submit\\"]",')
			script_lines.append(f'                    "button:not([disabled])",')
			script_lines.append(f'                    "[data-testid*=\\"button\\"]",')
			script_lines.append(f'                    "[aria-label*=\\"button\\"]",')
			script_lines.append(f'                    "button[data-testid]",')
			script_lines.append(f'                    "button[aria-label]",')
			# Add trash icon detection as fallback for any click action
			script_lines.append(f'                    "[data-testid*=\\"delete\\"]",')
			script_lines.append(f'                    "[data-testid*=\\"trash\\"]",')
			script_lines.append(f'                    "[aria-label*=\\"delete\\"]",')
			script_lines.append(f'                    "[aria-label*=\\"trash\\"]",')
			script_lines.append(f'                    "button:has(svg[data-testid*=\\"delete\\"])",')
			script_lines.append(f'                    "button:has(svg[data-testid*=\\"trash\\"])",')
			script_lines.append(f'                    "button:has(svg[aria-label*=\\"delete\\"])",')
			script_lines.append(f'                    "button:has(svg[aria-label*=\\"trash\\"])",')
			# script_lines.append(f'                    "[role=\\"button\\"]:not([disabled])",')  # Commented out - not working reliably
			# script_lines.append(f'                    "button",')  # Commented out - too generic, causes issues
			# script_lines.append(f'                    "input[type=\\"button\\"]"')  # Commented out - not working reliably
			script_lines.append(f'                ]')
			script_lines.append(f'                for selector in click_selectors:')
			script_lines.append(f'                    try:')
			script_lines.append(f'                        print(f"    Trying fallback selector: {{selector}}")')
			script_lines.append(f'                        await _try_locate_and_act(page, selector, "click", step_info={json.dumps(step_info_str)})')
			script_lines.append(f'                        print(f"  ✅ Successfully clicked with selector: {{selector}}")')
			script_lines.append(f'                        break')
			script_lines.append(f'                    except Exception as fallback_error:')
			script_lines.append(f'                        print(f"    Fallback selector {{selector}} failed: {{fallback_error}}")')
			script_lines.append(f'                        continue')
			script_lines.append(f'            except Exception as e:')
			script_lines.append(f'                print(f"  ❌ All fallback strategies failed for ({step_info_str}): {{e}}", file=sys.stderr)')
			# Removed unnecessary wait_for_timeout(2000) - no longer needed
		return script_lines

	def _map_scroll_down(self, params: dict, step_info_str: str, **kwargs) -> list[str]:
		amount = params.get('amount')
		script_lines = []
		if amount and isinstance(amount, int):
			script_lines.append(f'            print(f"Scrolling down by {amount} pixels ({step_info_str})")')
			script_lines.append(f"            await page.evaluate('window.scrollBy(0, {amount})')")
		else:
			script_lines.append(f'            print(f"Scrolling down by one page height ({step_info_str})")')
			script_lines.append("            await page.evaluate('window.scrollBy(0, window.innerHeight)')")
		# Removed unnecessary wait_for_timeout(500) - no longer needed
		return script_lines

	def _map_scroll_up(self, params: dict, step_info_str: str, **kwargs) -> list[str]:
		amount = params.get('amount')
		script_lines = []
		if amount and isinstance(amount, int):
			script_lines.append(f'            print(f"Scrolling up by {amount} pixels ({step_info_str})")')
			script_lines.append(f"            await page.evaluate('window.scrollBy(0, -{amount})')")
		else:
			script_lines.append(f'            print(f"Scrolling up by one page height ({step_info_str})")')
			script_lines.append("            await page.evaluate('window.scrollBy(0, -window.innerHeight)')")
		# Removed unnecessary wait_for_timeout(500) - no longer needed
		return script_lines

	def _map_send_keys(self, params: dict, step_info_str: str, **kwargs) -> list[str]:
		keys = params.get('keys')
		script_lines = []
		if keys and isinstance(keys, str):
			escaped_keys = json.dumps(keys)
			script_lines.append(f'            print(f"Sending keys: {keys} ({step_info_str})")')
			script_lines.append(f'            await page.keyboard.press({escaped_keys})')
			# Removed unnecessary wait_for_timeout(500) - no longer needed
		else:
			script_lines.append(f'            # Skipping send_keys ({step_info_str}): missing or invalid keys')
		return script_lines

	def _map_go_back(self, params: dict, step_info_str: str, **kwargs) -> list[str]:
		goto_timeout = self._get_goto_timeout()
		return [
			f'            print(f"Navigating back using browser history ({step_info_str})")',
			f'            await page.go_back(timeout={goto_timeout}, wait_until="domcontentloaded")',
			# Removed wait_for_load_state for faster execution - go_back already waits
		]

	def _map_open_tab(self, params: dict, step_info_str: str, **kwargs) -> list[str]:
		url = params.get('url')
		goto_timeout = self._get_goto_timeout()
		script_lines = []
		if url and isinstance(url, str):
			escaped_url = json.dumps(url)
			script_lines.append(f'            print(f"Opening new tab and navigating to: {url} ({step_info_str})")')
			script_lines.append('            page = await context.new_page()')
			script_lines.append(f'            await page.goto({escaped_url}, timeout={goto_timeout}, wait_until="domcontentloaded")')
			script_lines.append('            await page.bring_to_front()  # Bring new tab to front')
			# Removed wait_for_load_state for faster execution - goto already waits
			self._page_counter += 1  # Increment page counter
		else:
			script_lines.append(f'            # Skipping open_tab ({step_info_str}): missing or invalid url')
		return script_lines

	def _map_close_tab(self, params: dict, step_info_str: str, **kwargs) -> list[str]:
		page_id = params.get('page_id')
		script_lines = []
		if page_id is not None:
			script_lines.extend(
				[
					f'            print(f"Attempting to close tab with page_id {page_id} ({step_info_str})")',
					f'            if {page_id} < len(context.pages):',
					f'                target_page = context.pages[{page_id}]',
					'                await target_page.close()',
					# Removed unnecessary wait_for_timeout(500) - no longer needed
					'                if context.pages: page = context.pages[-1]',  # Switch to last page
					'                else:',
					"                    print('  Warning: No pages left after closing tab. Cannot switch.', file=sys.stderr)",
					'                    # Optionally, create a new page here if needed: page = await context.new_page()',
					'                if page: await page.bring_to_front()',  # Bring to front if page exists
					'            else:',
					f'                print(f"  Warning: Tab with page_id {page_id} not found to close ({step_info_str})", file=sys.stderr)',
				]
			)
		else:
			script_lines.append(f'            # Skipping close_tab ({step_info_str}): missing page_id')
		return script_lines

	def _map_switch_tab(self, params: dict, step_info_str: str, **kwargs) -> list[str]:
		page_id = params.get('page_id')
		url = params.get('url')  # Try to get URL as fallback
		script_lines = []
		if page_id is not None:
			script_lines.extend(
				[
					f'            print(f"Switching to tab with page_id {page_id} ({step_info_str})")',
					f'            if {page_id} < len(context.pages):',
					f'                page = context.pages[{page_id}]',
					'                await page.bring_to_front()',
					# Removed wait_for_load_state for faster execution
					'            else:',
					f'                print(f"  Warning: Tab with page_id {page_id} not found to switch ({step_info_str})", file=sys.stderr)',
				]
			)
		elif url:
			# Fallback: try to find tab by URL
			escaped_url = json.dumps(url)
			script_lines.extend(
				[
					f'            print(f"Switching to tab by URL: {url} ({step_info_str})")',
					f'            found_tab = False',
					f'            for tab_page in context.pages:',
					f'                if {escaped_url} in tab_page.url:',
					f'                    page = tab_page',
					f'                    await page.bring_to_front()',
					f'                    print(f"  ✅ Switched to tab with URL: {{tab_page.url}}")',
					f'                    found_tab = True',
					f'                    break',
					f'            if not found_tab:',
					f'                print(f"  Warning: Tab with URL containing {url} not found ({step_info_str})", file=sys.stderr)',
					f'                # Fallback: switch to last tab',
					f'                if context.pages:',
					f'                    page = context.pages[-1]',
					f'                    await page.bring_to_front()',
					f'                    print(f"  ⚠️ Switched to last available tab instead")',
				]
			)
		else:
			# No page_id or URL - try to switch to last tab as fallback
			script_lines.extend(
				[
					f'            print(f"Switching to last tab (page_id not provided) ({step_info_str})")',
					f'            if context.pages:',
					f'                page = context.pages[-1]',
					f'                await page.bring_to_front()',
					f'                print(f"  ✅ Switched to last available tab")',
					f'            else:',
					f'                print(f"  Warning: No tabs available to switch ({step_info_str})", file=sys.stderr)',
				]
			)
		return script_lines

	def _map_search_google(self, params: dict, step_info_str: str, **kwargs) -> list[str]:
		query = params.get('query')
		goto_timeout = self._get_goto_timeout()
		script_lines = []
		if query and isinstance(query, str):
			clean_query = f'replace_sensitive_data({json.dumps(query)}, SENSITIVE_DATA)'
			search_url_expression = f'f"https://www.google.com/search?q={{ urllib.parse.quote_plus({clean_query}) }}&udm=14"'
			script_lines.extend(
				[
					f'            search_url = {search_url_expression}',
					f'            print(f"Searching Google for query related to: {{ {clean_query} }} ({step_info_str})")',
					f'            await page.goto(search_url, timeout={goto_timeout}, wait_until="domcontentloaded")',
					# Removed wait_for_load_state for faster execution - goto already waits
				]
			)
		else:
			script_lines.append(f'            # Skipping search_google ({step_info_str}): missing or invalid query')
		return script_lines

	def _map_drag_drop(self, params: dict, step_info_str: str, **kwargs) -> list[str]:
		source_sel = params.get('element_source')
		target_sel = params.get('element_target')
		source_coords = (params.get('coord_source_x'), params.get('coord_source_y'))
		target_coords = (params.get('coord_target_x'), params.get('coord_target_y'))
		script_lines = [f'            print(f"Attempting drag and drop ({step_info_str})")']
		if source_sel and target_sel:
			escaped_source = json.dumps(source_sel)
			escaped_target = json.dumps(target_sel)
			script_lines.append(f'            await page.drag_and_drop({escaped_source}, {escaped_target})')
			script_lines.append(f"            print(f'  Dragged element {escaped_source} to {escaped_target}')")
		elif all(c is not None for c in source_coords) and all(c is not None for c in target_coords):
			sx, sy = source_coords
			tx, ty = target_coords
			script_lines.extend(
				[
					f'            await page.mouse.move({sx}, {sy})',
					'            await page.mouse.down()',
					f'            await page.mouse.move({tx}, {ty})',
					'            await page.mouse.up()',
					f"            print(f'  Dragged from ({sx},{sy}) to ({tx},{ty})')",
				]
			)
		else:
			script_lines.append(
				f'            # Skipping drag_drop ({step_info_str}): requires either element selectors or full coordinates'
			)
		# Removed unnecessary wait_for_timeout(500) - no longer needed
		return script_lines

	def _map_extract_content(self, params: dict, step_info_str: str, **kwargs) -> list[str]:
		goal = params.get('goal', 'content')
		logger.warning(f"Action 'extract_content' ({step_info_str}) cannot be directly translated to Playwright script.")
		return [f'            # Action: extract_content (Goal: {goal}) - Skipped in Playwright script ({step_info_str})']

	def _map_click_download_button(
		self, params: dict, history_item: dict, action_index_in_step: int, step_info_str: str, **kwargs
	) -> list[str]:
		index = params.get('index')
		selector = self._get_selector_for_action(history_item, action_index_in_step)
		download_dir_in_script = "'./files'"  # Default
		# if self.context_config and self.context_config.save_downloads_path:
		# 	download_dir_in_script = repr(self.context_config.save_downloads_path)

		script_lines = []
		if selector and index is not None:
			script_lines.append(
				f'            print(f"Attempting to download file by clicking element ({selector}) ({step_info_str})")'
			)
			script_lines.append('            try:')
			script_lines.append(
				'                async with page.expect_download(timeout=120000) as download_info:'
			)  # 2 min timeout
			step_info_for_download = f'{step_info_str} (triggering download)'
			script_lines.append(
				f'                    await _try_locate_and_act(page, {json.dumps(selector)}, "click", step_info={json.dumps(step_info_for_download)})'
			)
			script_lines.append('                download = await download_info.value')
			script_lines.append(f'                configured_download_dir = {download_dir_in_script}')
			script_lines.append('                download_dir_path = Path(configured_download_dir).resolve()')
			script_lines.append('                download_dir_path.mkdir(parents=True, exist_ok=True)')
			script_lines.append(
				"                base, ext = os.path.splitext(download.suggested_filename or f'download_{{len(list(download_dir_path.iterdir())) + 1}}.tmp')"
			)
			script_lines.append('                counter = 1')
			script_lines.append("                download_path_obj = download_dir_path / f'{base}{ext}'")
			script_lines.append('                while download_path_obj.exists():')
			script_lines.append("                    download_path_obj = download_dir_path / f'{base}({{counter}}){ext}'")
			script_lines.append('                    counter += 1')
			script_lines.append('                await download.save_as(str(download_path_obj))')
			script_lines.append("                print(f'  File downloaded successfully to: {str(download_path_obj)}')")
			script_lines.append('            except PlaywrightActionError as pae:')
			script_lines.append('                raise pae')  # Re-raise to stop script
			script_lines.append('            except Exception as download_err:')
			script_lines.append(
				f"                raise PlaywrightActionError(f'Download failed for {step_info_str}: {{download_err}}') from download_err"
			)
		else:
			script_lines.append(
				f'            # Skipping click_download_button ({step_info_str}): missing index ({index}) or selector ({selector})'
			)
		return script_lines

	def _map_done(self, params: dict, step_info_str: str, **kwargs) -> list[str]:
		script_lines = []
		if isinstance(params, dict):
			final_text = params.get('text', '')
			success_status = params.get('success', False)
			escaped_final_text_with_placeholders = json.dumps(str(final_text))
			script_lines.append(f'            print("\\n--- Task marked as Done by agent ({step_info_str}) ---")')
			script_lines.append(f'            print(f"Agent reported success: {success_status}")')
			script_lines.append('            # Final Message from agent (may contain placeholders):')
			script_lines.append(
				f'            final_message = replace_sensitive_data({escaped_final_text_with_placeholders}, SENSITIVE_DATA)'
			)
			script_lines.append('            print(final_message)')
		else:
			script_lines.append(f'            print("\\n--- Task marked as Done by agent ({step_info_str}) ---")')
			script_lines.append('            print("Success: N/A (invalid params)")')
			script_lines.append('            print("Final Message: N/A (invalid params)")')
		return script_lines

	def _map_action_to_playwright(
		self,
		action_dict: dict,
		history_item: dict,
		previous_history_item: dict | None,
		action_index_in_step: int,
		step_info_str: str,
	) -> list[str]:
		"""
		Translates a single action dictionary into Playwright script lines using dictionary dispatch.
		"""
		if not isinstance(action_dict, dict) or not action_dict:
			return [f'            # Invalid action format: {action_dict} ({step_info_str})']

		action_type = next(iter(action_dict.keys()), None)
		params = action_dict.get(action_type)

		if not action_type or params is None:
			if action_dict == {}:
				return [f'            # Empty action dictionary found ({step_info_str})']
			return [f'            # Could not determine action type or params: {action_dict} ({step_info_str})']

		# Get the handler function from the dictionary
		handler = self._action_handlers.get(action_type)

		if handler:
			# Call the specific handler method
			return handler(
				params=params,
				history_item=history_item,
				action_index_in_step=action_index_in_step,
				step_info_str=step_info_str,
				action_type=action_type,  # Pass action_type for legacy handling etc.
				previous_history_item=previous_history_item,
			)
		else:
			# Handle unsupported actions
			logger.warning(f'Unsupported action type encountered: {action_type} ({step_info_str})')
			return [f'            # Unsupported action type: {action_type} ({step_info_str})']

	def generate_script_content(self) -> str:
		"""Generates the full Playwright script content as a string."""
		script_lines = []
		self._page_counter = 0  # Reset page counter for new script generation

		if not self._imports_helpers_added:
			script_lines.extend(self._get_imports_and_helpers())
			self._imports_helpers_added = True

		# Read helper script content FIRST (needed for SENSITIVE_DATA loading)
		helper_script_path = Path(__file__).parent / 'playwright_script_helpers.py'
		try:
			with open(helper_script_path, encoding='utf-8') as f_helper:
				helper_script_content = f_helper.read()
		except FileNotFoundError:
			logger.error(f'Helper script not found at {helper_script_path}. Cannot generate script.')
			return '# Error: Helper script file missing.'
		except Exception as e:
			logger.error(f'Error reading helper script {helper_script_path}: {e}')
			return f'# Error: Could not read helper script: {e}'

		# Add the helper script content before sensitive data definitions
		script_lines.append('\n# --- Helper Functions (from playwright_script_helpers.py) ---')
		script_lines.append(helper_script_content)
		script_lines.append('# --- End Helper Functions ---')

		# Now define SENSITIVE_DATA using the helper functions
		script_lines.extend(self._get_sensitive_data_definitions())

		# Generate browser launch and context creation code
		browser_launch_args = self._generate_browser_launch_args()
		# context_options = self._generate_context_options()
		# Determine browser type (defaulting to chromium)
		browser_type = 'chromium'
		# if self.browser_config and self.browser_config.browser_class in ['firefox', 'webkit']:
		# 	browser_type = self.browser_config.browser_class

		script_lines.extend(
			[
				'async def run_generated_script():',
				'    global SENSITIVE_DATA',  # Ensure sensitive data is accessible
				'    async with async_playwright() as p:',
				'        browser = None',
				'        context = None',
				'        page = None',
				'        exit_code = 0 # Default success exit code',
				'        try:',
				f"            print('Launching {browser_type} browser...')",
				# Use generated launch args, remove slow_mo
				f'            browser = await p.{browser_type}.launch({browser_launch_args})',
				# Create context after browser launch
				'            context = await browser.new_context()',
				"            print('Browser context created.')",
			]
		)

		# Add cookie loading logic if cookies_file is specified
		# if self.context_config and self.context_config.cookies_file:
		# 	cookies_file_path = repr(self.context_config.cookies_file)
		# 	script_lines.extend(
		# 		[
		# 			'            # Load cookies if specified',
		# 			f'            cookies_path = {cookies_file_path}',
		# 			'            if cookies_path and os.path.exists(cookies_path):',
		# 			'                try:',
		# 			"                    with open(cookies_path, 'r', encoding='utf-8') as f_cookies:",
		# 			'                        cookies = json.load(f_cookies)',
		# 			'                        # Validate sameSite attribute',
		# 			"                        valid_same_site = ['Strict', 'Lax', 'None']",
		# 			'                        for cookie in cookies:',
		# 			"                            if 'sameSite' in cookie and cookie['sameSite'] not in valid_same_site:",
		# 			'                                print(f\'  Warning: Fixing invalid sameSite value "{{cookie["sameSite"]}}" to None for cookie {{cookie.get("name")}}\', file=sys.stderr)',
		# 			"                                cookie['sameSite'] = 'None'",
		# 			'                        await context.add_cookies(cookies)',
		# 			"                        print(f'  Successfully loaded {{len(cookies)}} cookies from {{cookies_path}}')",
		# 			'                except Exception as cookie_err:',
		# 			"                    print(f'  Warning: Failed to load or add cookies from {{cookies_path}}: {{cookie_err}}', file=sys.stderr)",
		# 			'            else:',
		# 			'                if cookies_path:',  # Only print if a path was specified but not found
		# 			"                    print(f'  Cookie file not found at: {cookies_path}')",
		# 			'',
		# 		]
		# 	)

		# Get initial URL from history if available
		initial_url = None
		if self.history and len(self.history) > 0:
			first_step = self.history[0]
			if isinstance(first_step, dict):
				state = first_step.get("state", {})
				if isinstance(state, dict):
					initial_url = state.get("url")

		script_lines.extend(
			[
				'            # Initial page handling',
				'            if context.pages:',
				'                page = context.pages[0]',
				"                print('Using initial page provided by context.')",
				'            else:',
				'                page = await context.new_page()',
				"                print('Created a new page as none existed.')",
				"            print('\\n--- Starting Generated Script Execution ---')",
			]
		)

		# Add initial navigation if URL is available
		if initial_url:
			script_lines.extend([
				f'            # Navigate to initial URL',
				f'            print(f"Navigating to: {initial_url}")',
				f'            await page.goto({json.dumps(initial_url)}, timeout=90000, wait_until="domcontentloaded")',
				# Removed wait_for_load_state for faster execution - goto already waits
			])
		
		# Add success detection function
		script_lines.extend([
			'            # Function to check if login was successful',
			'            def check_login_success():',
			'                current_url = page.url',
			'                return "login" not in current_url.lower()',
			'',
			'            # Function to handle account selection (generic for Jeeves workflows)',
			'            async def handle_account_selection():',
			'                try:',
			'                    page_title = await page.title()',
			'                    if "select" in page_title.lower() and "account" in page_title.lower():',
			'                        print(f"  🔍 Detected account selection page: {page_title}")',
			'                        # Try to select the first available account',
			'                        account_selectors = [',
			'                            # Generic account selectors - no hardcoded email addresses',
			'                            "[data-testid*=\'account\']",',
			'                            ".account-card",',
			'                            "[data-testid*=\'select\']",',
			'                            # ".account-option",',  # Commented out - not working reliably
			'                            # "[role=\'button\']",',  # Commented out - not working reliably
			'                            # "button"',  # Commented out - too generic, causes issues
			'                        ]',
			'                        ',
			'                        for selector in account_selectors:',
			'                            try:',
			'                                print(f"    Trying account selector: {selector}")',
			'                                element = await page.wait_for_selector(selector, timeout=3000, state="visible")',
			'                                if element:',
			'                                    await element.scroll_into_view_if_needed()',
			'                                    # Removed unnecessary wait_for_timeout(300) - no longer needed',
			'                                    await element.click()',
			'                                    print(f"  ✅ Selected account using: {selector}")',
			'                                    return True',
			'                            except:',
			'                                continue',
			'                        ',
			'                        print(f"  ⚠️ Could not find account selection element")',
			'                        return False',
			'                except:',
			'                    return False',
			'',
		])

		action_counter = 0
		stop_processing_steps = False
		previous_item_dict = None
		# print(f"History: {self.history}", "the history inside a function.")
		# print(f"History length: {type(self.history)}", "the type ")
		for step_index, item_dict in enumerate(self.history):
			# Handle case where item_dict might be a JSON string
			if isinstance(item_dict, str):
				try:
					item_dict = json.loads(item_dict)
				except json.JSONDecodeError as e:
					logger.warning(f'Skipping step {step_index + 1}: Could not parse JSON string: {e}')
					script_lines.append(f'\n            # --- Step {step_index + 1}: Skipped (Invalid JSON) ---')
					previous_item_dict = item_dict
					continue

			if stop_processing_steps:
				break

			if not isinstance(item_dict, dict):
				logger.warning(f'Skipping step {step_index + 1}: Item is not a dictionary ({type(item_dict)})')
				script_lines.append(f'\n            # --- Step {step_index + 1}: Skipped (Invalid Format) ---')
				previous_item_dict = item_dict
				continue

			script_lines.append(f'\n            # --- Step {step_index + 1} ---')
			model_output = item_dict.get('model_output')

			if not isinstance(model_output, dict) or 'action' not in model_output:
				script_lines.append('            # No valid model_output or action found for this step')
				previous_item_dict = item_dict
				continue

			actions = model_output.get('action')
			if not isinstance(actions, list):
				script_lines.append(f'            # Actions format is not a list: {type(actions)}')
				previous_item_dict = item_dict
				continue

			for action_index_in_step, action_detail in enumerate(actions):
				action_counter += 1
				script_lines.append(f'            # Action {action_counter}')

				step_info_str = f'Step {step_index + 1}, Action {action_index_in_step + 1}'
				action_lines = self._map_action_to_playwright(
					action_dict=action_detail,
					history_item=item_dict,
					previous_history_item=previous_item_dict,
					action_index_in_step=action_index_in_step,
					step_info_str=step_info_str,
				)
				script_lines.extend(action_lines)
				
				# Check for account selection after each action
				script_lines.append('            # Check if we need to handle account selection')
				script_lines.append('            await handle_account_selection()')

				action_type = next(iter(action_detail.keys()), None) if isinstance(action_detail, dict) else None
				if action_type == 'done':
					stop_processing_steps = True
					break

			previous_item_dict = item_dict

		# Updated final block to include sys.exit
		script_lines.extend(
			[
				'        except PlaywrightActionError as pae:',  # Catch specific action errors
				"            print(f'\\n--- Playwright Action Error: {pae} ---', file=sys.stderr)",
				'            exit_code = 1',  # Set exit code to failure
				'        except Exception as e:',
				"            print(f'\\n--- An unexpected error occurred: {e} ---', file=sys.stderr)",
				'            import traceback',
				'            traceback.print_exc()',
				'            exit_code = 1',  # Set exit code to failure
				'        finally:',
				"            print('\\n--- Generated Script Execution Finished ---')",
				"            print('Closing browser/context...')",
				'            if context:',
				'                 try: await context.close()',
				"                 except Exception as ctx_close_err: print(f'  Warning: could not close context: {ctx_close_err}', file=sys.stderr)",
				'            if browser:',
				'                 try: await browser.close()',
				"                 except Exception as browser_close_err: print(f'  Warning: could not close browser: {browser_close_err}', file=sys.stderr)",
				"            print('Browser/context closed.')",
				'            # Exit with the determined exit code',
				'            if exit_code != 0:',
				"                print(f'Script finished with errors (exit code {exit_code}).', file=sys.stderr)",
				'                sys.exit(exit_code)',  # Exit with non-zero code on error
				'',
				'# --- Script Entry Point ---',
				"if __name__ == '__main__':",
				'    import argparse',
				'    parser = argparse.ArgumentParser(description="Run generated Playwright script")',
				'    parser.add_argument("--variables", "-v", dest="variables_file",',
				'                        default=_DEFAULT_VARIABLES_PATH,',
				'                        help=f"Path to JSON file containing sensitive data variables (default: {{_DEFAULT_VARIABLES_PATH}})")',
				'    args = parser.parse_args()',
				'    ',
				'    # Normalize paths for comparison (expand user dir and resolve if exists)',
				'    def normalize_path(p):',
				'        expanded = os.path.expanduser(p)',
				'        path_obj = Path(expanded)',
				'        if path_obj.exists():',
				'            return str(path_obj.resolve())',
				'        # If path doesn\'t exist, return normalized absolute path',
				'        if path_obj.is_absolute():',
				'            return str(path_obj)',
				'        return str(Path.cwd() / path_obj)',
				'    ',
				'    default_path_normalized = normalize_path(_DEFAULT_VARIABLES_PATH)',
				'    provided_path_normalized = normalize_path(args.variables_file)',
				'    ',
				'    # Load SENSITIVE_DATA from the specified file (default or overridden)',
				'    variables_file_to_use = args.variables_file',
				'    ',
				'    if provided_path_normalized != default_path_normalized:',
				'        print(f"Loading variables from: {variables_file_to_use}")',
				'    else:',
				'        print(f"Loading variables from default file: {_DEFAULT_VARIABLES_PATH}")',
				'    ',
				'    # Load the variables file',
				'    if _ENV_VARS_MAPPING:',
				'        SENSITIVE_DATA = get_sensitive_data(variables_file_to_use, env_vars=_ENV_VARS_MAPPING)',
				'    else:',
				'        SENSITIVE_DATA = get_sensitive_data(variables_file_to_use)',
				'    ',
				'    # Verify that data was loaded',
				'    if not SENSITIVE_DATA:',
				'        print(f"Warning: No variables loaded from {variables_file_to_use}. Check if file exists and contains valid JSON.", file=sys.stderr)',
				'    else:',
				'        print(f"✅ Loaded {len(SENSITIVE_DATA)} variable(s): {list(SENSITIVE_DATA.keys())}")',
				'    ',
				"    if os.name == 'nt':",
				'        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())',
				'    asyncio.run(run_generated_script())',
			]
		)

		return '\n'.join(script_lines)


# Supported models configuration
SUPPORTED_MODELS = {
    # Google models
    "gemini-flash-latest": {"provider": "google", "env_key": "GOOGLE_API_KEY"},
    "gemini-2.5-flash": {"provider": "google", "env_key": "GOOGLE_API_KEY"},
    "gemini-pro": {"provider": "google", "env_key": "GOOGLE_API_KEY"},
    
    # OpenAI models
    "o3": {"provider": "openai", "env_key": "OPENAI_API_KEY"},
    "o3-mini": {"provider": "openai", "env_key": "OPENAI_API_KEY"},
    "gpt-4o": {"provider": "openai", "env_key": "OPENAI_API_KEY"},
    "gpt-4": {"provider": "openai", "env_key": "OPENAI_API_KEY"},
    "gpt-3.5-turbo": {"provider": "openai", "env_key": "OPENAI_API_KEY"},
    
    # Anthropic models
    "claude-sonnet-4-0": {"provider": "anthropic", "env_key": "ANTHROPIC_API_KEY"},
    "claude-3-5-sonnet": {"provider": "anthropic", "env_key": "ANTHROPIC_API_KEY"},
    "claude-3-opus": {"provider": "anthropic", "env_key": "ANTHROPIC_API_KEY"},
    
    # Azure OpenAI models
    "o4-mini": {"provider": "azure_openai", "env_key": "AZURE_OPENAI_API_KEY", "endpoint_key": "AZURE_OPENAI_ENDPOINT"},
    
    # Groq models
    "meta-llama/llama-4-maverick-17b-128e-instruct": {"provider": "groq", "env_key": "GROQ_API_KEY"},
    "llama-3.1-70b-versatile": {"provider": "groq", "env_key": "GROQ_API_KEY"},
    
    # Ollama models
    "llama3.1:8b": {"provider": "ollama", "env_key": None},
    "llama3.1:70b": {"provider": "ollama", "env_key": None},
    
    # Qwen models (via OpenAI-compatible API)
    "qwen-vl-max": {"provider": "qwen", "env_key": "ALIBABA_CLOUD"},
    
    # ModelScope models
    "Qwen/Qwen2.5-VL-72B-Instruct": {"provider": "modelscope", "env_key": "MODELSCOPE_API_KEY"},
}


def get_supported_models_list() -> str:
    """Return a formatted string of all supported models."""
    providers = {}
    for model, config in SUPPORTED_MODELS.items():
        provider = config["provider"]
        if provider not in providers:
            providers[provider] = []
        providers[provider].append(model)
    
    lines = ["Supported Models:"]
    for provider, models in sorted(providers.items()):
        lines.append(f"\n  {provider.replace('_', ' ').title()}:")
        for model in sorted(models):
            lines.append(f"    - {model}")
    
    return "\n".join(lines)


def update_env_file(env_key: str, api_key: str, endpoint: Optional[str] = None, region: Optional[str] = None, endpoint_key: Optional[str] = None, region_key: Optional[str] = None):
    """Update or create .env file with API key and optional endpoint/region."""
    env_path = Path(".env")
    
    # Read existing .env file if it exists
    env_vars = {}
    if env_path.exists():
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    env_vars[key.strip()] = value.strip()
    
    # Update with new values
    env_vars[env_key] = api_key
    if endpoint and endpoint_key:
        env_vars[endpoint_key] = endpoint
    if region and region_key:
        env_vars[region_key] = region
    
    # Write back to .env file
    with open(env_path, 'w') as f:
        for key, value in env_vars.items():
            f.write(f"{key}={value}\n")
    
    # Reload environment variables
    load_dotenv(override=True)


def collect_api_key(model: str, config: dict) -> str:
    """Collect API key from user input."""
    env_key = config.get("env_key")
    if env_key is None:
        return None  # No API key needed (e.g., Ollama)
    
    # Check if API key already exists in environment
    existing_key = os.getenv(env_key)
    if existing_key:
        use_existing = input(f"Found existing {env_key} in environment. Use it? (y/n): ").strip().lower()
        if use_existing == 'y':
            return existing_key
    
    # Collect new API key
    print(f"\nPlease provide your API key for {model}")
    print(f"Required environment variable: {env_key}")
    api_key = input(f"Enter your {env_key}: ").strip()
    
    if not api_key:
        raise ValueError(f"API key is required for model {model}")
    
    # Save to .env file
    update_env_file(env_key, api_key)
    print(f"✅ API key saved to .env file")
    
    return api_key


def create_llm_instance(model: str, api_key: Optional[str] = None) -> Any:
    """
    Create an LLM instance based on the model name.
    
    Args:
        model: Model name (e.g., "gemini-2.5-flash", "o3", "claude-sonnet-4-0")
        api_key: Optional API key. If not provided, will be collected from user or environment.
    
    Returns:
        LLM instance
    
    Raises:
        ValueError: If model is not supported
    """
    if model not in SUPPORTED_MODELS:
        error_msg = f"\n❌ Error: Model '{model}' is not supported.\n\n"
        error_msg += get_supported_models_list()
        raise ValueError(error_msg)
    
    config = SUPPORTED_MODELS[model]
    provider = config["provider"]
    
    # Handle API key collection and storage
    env_key = config.get("env_key")
    if env_key:
        # If API key is provided as parameter, save it to .env and use it
        if api_key:
            update_env_file(env_key, api_key)
            print(f"✅ API key saved to .env file")
        else:
            # Check if API key exists in environment
            existing_key = os.getenv(env_key)
            if existing_key:
                use_existing = input(f"Found existing {env_key} in environment. Use it? (y/n): ").strip().lower()
                if use_existing == 'y':
                    api_key = existing_key
                else:
                    api_key = collect_api_key(model, config)
            else:
                # Collect API key from user
                api_key = collect_api_key(model, config)
        
        # Verify API key is available
        if not api_key:
            raise ValueError(f"API key not found. Please set {env_key} in your .env file or provide it when prompted.")
        
        # Set environment variable for this session (browser-use reads from env)
        os.environ[env_key] = api_key
    
    # Initialize model based on provider
    if provider == "google":
        return ChatGoogle(model=model, temperature=0.1)
    
    elif provider == "openai":
        return ChatOpenAI(model=model)
    
    elif provider == "anthropic":
        return ChatAnthropic(model=model)
    
    elif provider == "azure_openai":
        endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        if not endpoint:
            endpoint = input("Enter your Azure OpenAI endpoint: ").strip()
            if endpoint:
                update_env_file(env_key, api_key, endpoint=endpoint, endpoint_key="AZURE_OPENAI_ENDPOINT")
        return ChatAzureOpenAI(model=model)
    
    elif provider == "groq":
        return ChatGroq(model=model)
    
    elif provider == "ollama":
        return ChatOllama(model=model)
    
    elif provider == "qwen":
        base_url = 'https://dashscope-intl.aliyuncs.com/compatible-mode/v1'
        return ChatOpenAI(model=model, api_key=api_key, base_url=base_url)
    
    elif provider == "modelscope":
        base_url = 'https://api-inference.modelscope.cn/v1/'
        return ChatOpenAI(model=model, api_key=api_key, base_url=base_url)
    
    else:
        raise ValueError(f"Unknown provider: {provider}")


# Standalone function to run agent and generate script
async def main(task: str, llm, max_steps: int = 100, output_dir: Optional[str] = None, variables_file_path: Optional[str] = None, generate_script: bool = True) -> str:
    """Run an agent task and generate a Playwright script from the execution history.
    
    Args:
        task: The task description for the agent
        llm: The LLM instance to use
        max_steps: Maximum number of steps for the agent
        output_dir: Optional directory path to save the generated script. 
                   If None, saves to current directory.
        variables_file_path: Optional path to JSON file containing sensitive data variables.
        generate_script: If True (default), generates and saves a Playwright script. 
                        If False, skips script generation.
    """

    # # browser = Browser(
    # #     headless=False,  # Required for DevTools
    # #     # devtools = True,
	# # 	window_size={'width': 1800, 'height': 1080}
    #     # additional_args=[
    #     #     '--auto-open-devtools-for-tabs'  # Opens DevTools automatically for each tab
    #     # ]
    # )
    # Create and run the agent
    agent = Agent(
        task=task,
        llm=llm,
        override_system_message=SYSTEM_PROMPT,
        # browser=browser,
        # browser_config=self.browser_config,
        # context_config=self.context_config
    )
    
    # Run the agent
    result = await agent.run(max_steps=100)
    
    # Get the agent's execution history
    history_data = agent.history.model_dump()
    
    # Ensure history_data is a list of dictionaries
    if isinstance(history_data, dict) and 'history' in history_data:
        history_data = history_data['history']
    
    # Generate the Playwright script only if requested
    if generate_script:
        # Create a PlaywrightScriptGenerator instance with the history
        generator = PlaywrightScriptGenerator(
            history_list=history_data,
            sensitive_data_keys=['username', 'password', 'website'],
            variables_file_path=variables_file_path
        )
        
        # Generate the Playwright script
        script_content = generator.generate_script_content()
        
        # Save the generated script to a file
        from datetime import datetime
        output_filename = f"generated_playwright_{datetime.now().strftime('%Y%m%d_%H%M%S')}.py"
        
        # Configure output directory
        if output_dir:
            output_dir_path = Path(output_dir)
            output_dir_path.mkdir(parents=True, exist_ok=True)
            output_file = output_dir_path / output_filename
        else:
            output_file = Path(output_filename)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(script_content)
        
        print(f"Generated Playwright script saved to: {output_file}")
        print("You can now run the generated script independently with: python " + str(output_file))
        
        return script_content
    else:
        print("Script generation skipped (--no-generate-script flag was used)")
        return ""

def load_variables_from_json(json_file_path: str) -> Dict[str, Any]:
    """
    Load sensitive variables from a JSON file.
    
    Expected keys: username, password, website
    
    Args:
        json_file_path: Path to the JSON file containing variables
        
    Returns:
        Dictionary containing the variables
        
    Raises:
        FileNotFoundError: If the file doesn't exist
        json.JSONDecodeError: If the file is not valid JSON
        ValueError: If required keys are missing
    """
    file_path = Path(json_file_path)
    
    if not file_path.exists():
        raise FileNotFoundError(f"Variables file not found: {json_file_path}")
    
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    if not isinstance(data, dict):
        raise ValueError(f"Variables file must contain a JSON object (dict), got {type(data).__name__}")
    
    # Check for required keys
    required_keys = ['username', 'password', 'website']
    missing_keys = [key for key in required_keys if key not in data]
    if missing_keys:
        raise ValueError(f"Missing required keys in variables file: {', '.join(missing_keys)}")
    
    return data


def inject_variables_into_task(task: str, variables: Dict[str, Any]) -> str:
    """
    Inject variables into a task string by replacing placeholders.
    
    Replaces placeholders like {username}, {password}, {website} with values from variables.
    Also appends a context section with all variables at the end.
    
    Args:
        task: The task string (may contain placeholders like {key})
        variables: Dictionary containing variables to inject
        
    Returns:
        Task string with variables injected
    """
    modified_task = task
    
    # Replace placeholders in the format {key} with values from variables
    for key, value in variables.items():
        placeholder = f"{{{key}}}"
        if placeholder in modified_task:
            modified_task = modified_task.replace(placeholder, str(value))
            logger.debug(f"Replaced placeholder {placeholder} with value")
    
    # Append variables as context at the end (for any that weren't used as placeholders)
    context_lines = ["\n\n--- Variables Context ---"]
    for key, value in variables.items():
        # Only include keys that weren't already replaced as placeholders
        if f"{{{key}}}" not in task:
            context_lines.append(f"{key}: {value}")
    
    # Only append context if there are items to add
    if len(context_lines) > 1:
        modified_task += "\n" + "\n".join(context_lines)
    
    return modified_task


def read_task_from_file(file_path: str) -> Dict[str, Any]:
    """
    Read a task or task configuration from a file.
    
    Supports:
    - Plain text files: Just the task string, or multiple tasks separated by:
      - Lines starting with "---" or "===" (markdown-style separators)
      - Lines starting with "Task 1:", "Task 2:", etc.
      - Lines starting with "## Task" or "# Task"
      - Multiple blank lines (3+ consecutive blank lines)
    - JSON files: Can contain:
      - {"task": "..."} - Single task
      - {"base_template": "...", "variations": [...]} - Template with variations
      - {"variations": [...]} - Just variations (each with full task)
    
    Args:
        file_path: Path to the task file
        
    Returns:
        Dictionary with task configuration
    """
    file_path_obj = Path(file_path)
    
    if not file_path_obj.exists():
        raise FileNotFoundError(f"Task file not found: {file_path}")
    
    # Try to parse as JSON first
    try:
        with open(file_path_obj, 'r', encoding='utf-8') as f:
            content = f.read().strip()
            if content.startswith('{') or content.startswith('['):
                data = json.loads(content)
                return data
    except json.JSONDecodeError:
        # Not JSON, treat as plain text
        pass
    except Exception as e:
        logger.warning(f"Error parsing as JSON, treating as plain text: {e}")
    
    # Read as plain text
    with open(file_path_obj, 'r', encoding='utf-8') as f:
        task_content = f.read()
    
    # Detect multiple tasks in the text file
    tasks = _detect_multiple_tasks(task_content)
    
    if len(tasks) > 1:
        # Multiple tasks detected - convert to variations format
        variations = []
        for i, task in enumerate(tasks):
            task_text = task.strip()
            if task_text:  # Only add non-empty tasks
                variations.append({
                    "variation_id": f"task_{i + 1}",
                    "task": task_text
                })
        
        if variations:
            logger.info(f"Detected {len(variations)} tasks in text file. Will run in parallel.")
            return {"variations": variations}
    
    # Single task or no tasks detected
    task_content = task_content.strip()
    return {"task": task_content}


def _detect_multiple_tasks(content: str) -> List[str]:
    """
    Detect multiple tasks in a text file using various delimiters.
    
    Args:
        content: The file content as a string
        
    Returns:
        List of task strings
    """
    if not content or not content.strip():
        return []
    
    lines = content.split('\n')
    tasks = []
    current_task = []
    blank_line_count = 0
    
    # Common task separators
    separator_patterns = [
        r'^---+',  # Lines starting with ---
        r'^===+',  # Lines starting with ===
        r'^##+\s+Task',  # Lines starting with ## Task
        r'^#\s+Task',  # Lines starting with # Task
        r'^Task\s+\d+:',  # Lines starting with "Task 1:", "Task 2:", etc.
        r'^Task\s+\d+\.',  # Lines starting with "Task 1.", "Task 2.", etc.
    ]
    
    for i, line in enumerate(lines):
        # Check if this line is a separator
        is_separator = False
        for pattern in separator_patterns:
            if re.match(pattern, line.strip(), re.IGNORECASE):
                is_separator = True
                break
        
        if is_separator:
            # Save current task if it has content
            if current_task:
                tasks.append('\n'.join(current_task))
                current_task = []
            blank_line_count = 0
            continue
        
        # Check for multiple blank lines (3+ consecutive blank lines = task separator)
        if not line.strip():
            blank_line_count += 1
            if blank_line_count >= 3:
                # Save current task if it has content
                if current_task:
                    tasks.append('\n'.join(current_task))
                    current_task = []
                blank_line_count = 0
                continue
        else:
            blank_line_count = 0
        
        current_task.append(line)
    
    # Add the last task
    if current_task:
        tasks.append('\n'.join(current_task))
    
    # If we found multiple tasks, return them
    # Otherwise, return the original content as a single task
    if len(tasks) > 1:
        return tasks
    else:
        return [content]


async def run_task_from_file(file_path: str, llm=None, max_steps: int = 100, output_dir: Optional[str] = None, variables: Optional[Dict[str, Any]] = None, variables_file_path: Optional[str] = None, generate_script: bool = True, model: str = "gemini-2.5-flash"):
    """
    Read a task from a file and execute it.
    
    Args:
        file_path: Path to the task file
        llm: LLM instance (defaults to model factory if not provided)
        max_steps: Maximum steps for the agent
        output_dir: Optional directory path to save generated scripts.
                   Can also be specified in task_config as "output_dir".
        variables: Optional dictionary containing variables to inject into tasks.
                   If provided, will replace placeholders like {key} and append context.
        variables_file_path: Optional path to JSON file containing sensitive data variables.
                            This will be passed to the generated Playwright script.
        generate_script: If True (default), generates and saves a Playwright script.
                        If False, skips script generation.
        model: LLM model name to use (default: "gemini-2.5-flash"). Only used if llm is None.
        
    Returns:
        Generated script content or results
    """
    if llm is None:
        print(f"Initializing LLM model: {model}")
        try:
            llm = create_llm_instance(model)
            print(f"✅ Successfully initialized {model}")
        except ValueError as e:
            print(str(e))
            sys.exit(1)
        except Exception as e:
            print(f"❌ Error initializing model {model}: {e}")
            sys.exit(1)
    
    task_config = read_task_from_file(file_path)
    
    # Inject variables if provided
    if variables:
        logger.info("Injecting variables into task(s)")
        if "task" in task_config and "variations" not in task_config:
            # Single task
            task_config["task"] = inject_variables_into_task(task_config["task"], variables)
        elif "base_template" in task_config:
            # Template with variations
            task_config["base_template"] = inject_variables_into_task(task_config["base_template"], variables)
        elif "variations" in task_config:
            # Multiple tasks - inject into each variation
            for variation in task_config["variations"]:
                if "task" in variation:
                    variation["task"] = inject_variables_into_task(variation["task"], variables)
    
    # Determine output_dir: parameter > task_config > task file's directory
    if output_dir is None:
        output_dir = task_config.get("output_dir")
    
    # If still None, default to the task file's directory
    if output_dir is None and generate_script:
        task_file_path = Path(file_path).resolve()  # Resolve to absolute path
        output_dir = str(task_file_path.parent)
        print(f"ℹ️  Output directory not specified. Generated Playwright script will be saved to: {output_dir}")
    
    # Check if it's a single task
    if "task" in task_config and "variations" not in task_config:
        task = task_config["task"]
        print(f"Executing task from file: {file_path}")
        return await main(task, llm, max_steps, output_dir=output_dir, variables_file_path=variables_file_path, generate_script=generate_script)
    
    # Check if it's a template with variations
    if "base_template" in task_config and "variations" in task_config:
        base_template = task_config["base_template"]
        variations = task_config["variations"]
        max_concurrent = task_config.get("max_concurrent", 2)
        
        test_runner = DynamicTestRunner(base_template, llm, max_steps=100, output_dir=output_dir, variables_file_path=variables_file_path, generate_script=generate_script)
        print(f"Running {len(variations)} variations from file: {file_path}")
        
        # Check if sequential execution is requested
        if task_config.get("sequential", False):
            results = await test_runner.run_sequential_variations(variations)
        else:
            results = await test_runner.run_parallel_variations(variations, max_concurrent=max_concurrent)
        
        report = test_runner.generate_summary_report()
        print(report)
        
        # Save results if output file is specified
        if "output_file" in task_config:
            results_file = test_runner.save_results_to_file(task_config["output_file"])
            print(f"\nDetailed results saved to: {results_file}")
        else:
            results_file = test_runner.save_results_to_file()
            print(f"\nDetailed results saved to: {results_file}")
        
        return results
    
    # Check if it's just variations (each variation has full task)
    if "variations" in task_config and "base_template" not in task_config:
        variations = task_config["variations"]
        max_concurrent = task_config.get("max_concurrent", 3)  # Default to 3 concurrent tasks
        sequential = task_config.get("sequential", False)
        
        # Use parallel execution by default for multiple tasks
        if sequential or len(variations) == 1:
            # Sequential execution
            results = []
            for variation in variations:
                if "task" in variation:
                    variation_id = variation.get("variation_id", f"variation_{variations.index(variation)}")
                    task = variation["task"]
                    print(f"Executing variation: {variation_id}")
                    try:
                        script_content = await main(task, llm, max_steps, output_dir=output_dir, variables_file_path=variables_file_path, generate_script=generate_script)
                        results.append({
                            "variation_id": variation_id,
                            "success": True,
                            "script_content": script_content
                        })
                    except Exception as e:
                        logger.error(f"Error in variation {variation_id}: {e}")
                        results.append({
                            "variation_id": variation_id,
                            "success": False,
                            "error": str(e)
                        })
        else:
            # Parallel execution for multiple tasks
            print(f"Running {len(variations)} tasks in parallel (max {max_concurrent} concurrent)...")
            semaphore = asyncio.Semaphore(max_concurrent)
            
            async def run_single_task(variation):
                variation_id = variation.get("variation_id", f"variation_{variations.index(variation)}")
                task = variation.get("task")
                
                if not task:
                    return {
                        "variation_id": variation_id,
                        "success": False,
                        "error": "No task found in variation"
                    }
                
                async with semaphore:
                    print(f"Starting task: {variation_id}")
                    try:
                        script_content = await main(task, llm, max_steps, output_dir=output_dir, variables_file_path=variables_file_path, generate_script=generate_script)
                        print(f"✅ Completed task: {variation_id}")
                        return {
                            "variation_id": variation_id,
                            "success": True,
                            "script_content": script_content
                        }
                    except Exception as e:
                        logger.error(f"Error in variation {variation_id}: {e}")
                        print(f"❌ Failed task: {variation_id}")
                        return {
                            "variation_id": variation_id,
                            "success": False,
                            "error": str(e)
                        }
            
            # Run all tasks in parallel
            tasks_to_run = [run_single_task(v) for v in variations if "task" in v]
            results = await asyncio.gather(*tasks_to_run, return_exceptions=True)
            
            # Handle any exceptions that occurred
            processed_results = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    variation_id = variations[i].get("variation_id", f"variation_{i}")
                    processed_results.append({
                        "variation_id": variation_id,
                        "success": False,
                        "error": str(result)
                    })
                else:
                    processed_results.append(result)
            results = processed_results
        
        # Generate summary
        successful = sum(1 for r in results if r.get('success', False))
        print(f"\n{'='*50}")
        print(f"Completed {len(results)} tasks. {successful} successful, {len(results) - successful} failed.")
        print(f"{'='*50}")
        
        return results
    
    # If we get here, it's an invalid format
    raise ValueError(f"Invalid task file format. Expected 'task', 'base_template' with 'variations', or 'variations' with 'task' fields.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run automated tasks with sensitive data injection",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python AGENT_RUNNER.py prompt.txt --variables=credentials.json
  python AGENT_RUNNER.py task.txt --variables=config.json --max-steps 50
  python AGENT_RUNNER.py prompt.txt --variables=secrets.json --output-dir ./scripts
  python AGENT_RUNNER.py my_task.txt 100 ./output  # Backward compatible
  python AGENT_RUNNER.py task.txt --no-generate-script  # Skip script generation
  python AGENT_RUNNER.py task.txt --model gemini-pro  # Use different model

The variables.json file should contain:
  {
    "username": "user@example.com",
    "password": "secure_password",
    "website": "https://example.com"
  }
        """
    )
    
    parser.add_argument('file_path', help='Path to the prompt/task file (.txt or .json)')
    parser.add_argument('arg2', nargs='?', help='Optional: max_steps (int) or output_dir (string) - for backward compatibility')
    parser.add_argument('arg3', nargs='?', help='Optional: output_dir (string) if arg2 is max_steps, or max_steps (int) if arg2 is output_dir')
    parser.add_argument('--variables', '--vars', '-v',
                       dest='variables_path',
                       help='Path to JSON file containing variables (username, password, website)')
    parser.add_argument('--max-steps', type=int, default=None,
                       help='Maximum steps for the agent (overrides positional arg if provided)')
    parser.add_argument('--output-dir', default=None,
                       help='Directory to save generated scripts (overrides positional arg if provided)')
    parser.add_argument('--no-generate-script', action='store_true',
                       help='Skip generating Playwright script (default: script is generated)')
    parser.add_argument('--model', default='gemini-2.5-flash',
                       help='LLM model to use (default: gemini-2.5-flash). Use --list-models to see all supported models.')
    parser.add_argument('--list-models', action='store_true',
                       help='List all supported models and exit')
    
    # Parse arguments
    args = parser.parse_args()
    
    # Handle --list-models flag
    if args.list_models:
        print(get_supported_models_list())
        sys.exit(0)
    
    # Validate model if provided
    if args.model and args.model not in SUPPORTED_MODELS:
        print(f"\n❌ Error: Model '{args.model}' is not supported.\n")
        print(get_supported_models_list())
        print(f"\nUse --list-models to see all supported models.")
        sys.exit(1)
    file_path = args.file_path
    variables_path = args.variables_path
    
    # Handle backward compatibility: parse positional args (max_steps and/or output_dir)
    # But command-line flags take precedence
    max_steps = 100
    output_dir = None
    
    # Use command-line flags if provided, otherwise use positional args
    if args.max_steps is not None:
        max_steps = args.max_steps
    elif args.arg2:
        # Try to parse as integer (max_steps)
        try:
            max_steps = int(args.arg2)
            # If arg3 exists, it's output_dir
            if args.arg3:
                output_dir = args.arg3
        except ValueError:
            # arg2 is not an integer, treat as output_dir
            output_dir = args.arg2
            # If arg3 exists, try to parse as max_steps
            if args.arg3:
                try:
                    max_steps = int(args.arg3)
                except ValueError:
                    print(f"Warning: Invalid max_steps value '{args.arg3}', using default: {max_steps}")
    
    if args.output_dir is not None:
        output_dir = args.output_dir
    
    # Determine if script generation should be enabled (default: True)
    generate_script = not args.no_generate_script
    
    # Get model from arguments
    model = args.model
    
    # Check if it's a file path (exists as a file)
    # Expand user home directory and resolve to absolute path
    expanded_arg = os.path.expanduser(file_path)
    file_path_obj = Path(expanded_arg).resolve()
    if file_path_obj.exists() and file_path_obj.is_file():
        # It's a file path - read and execute task from file
        print(f"Reading task from file: {file_path}")
        try:
            # Load variables if provided
            variables = None
            if variables_path:
                print(f"Loading variables from: {variables_path}")
                try:
                    variables = load_variables_from_json(variables_path)
                    print(f"✅ Loaded variables: {', '.join(variables.keys())}")
                except Exception as e:
                    print(f"❌ Error loading variables: {e}", file=sys.stderr)
                    sys.exit(1)
            
            asyncio.run(run_task_from_file(file_path, max_steps=max_steps, output_dir=output_dir, variables=variables, variables_file_path=variables_path, generate_script=generate_script, model=model))
        except Exception as e:
            print(f"Error executing task from file: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()
            sys.exit(1)
    else:
        # File doesn't exist
        print(f"Error: '{file_path}' is not a valid file path.")
        print(f"Resolved path checked: {file_path_obj}")
        if not file_path_obj.exists():
            print(f"  - Path does not exist")
        elif not file_path_obj.is_file():
            print(f"  - Path exists but is not a file (might be a directory)")
        print("\nPlease provide a file path containing your task.")
        parser.print_help()
        sys.exit(1)