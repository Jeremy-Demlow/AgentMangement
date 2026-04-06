#!/usr/bin/env python3
"""
Invoke a Cortex Agent via REST API and capture response with tool usage details.

Usage:
    python invoke_agent.py <database> <schema> <agent_name> "<question>" <connection>

Example:
    python invoke_agent.py SNOWFLAKE_INTELLIGENCE AGENTS DONUT_ASSISTANT \
        "What is the most popular donut?" SFDEVREL_ENTERPRISE
"""

import os
import json
import sys
import snowflake.connector
import requests


def invoke_agent(database: str, schema: str, agent_name: str, question: str, connection_name: str) -> dict:
    """
    Invoke a Cortex Agent and return structured response with tool usage.

    Returns:
        dict with keys: question, answer, tool_uses, tool_results
    """
    conn = snowflake.connector.connect(connection_name=connection_name)

    cursor = conn.cursor()
    cursor.execute("SELECT CURRENT_ORGANIZATION_NAME(), CURRENT_ACCOUNT_NAME()")
    org, account = cursor.fetchone()

    # IMPORTANT: Replace underscores with hyphens in account URL for SSL compatibility
    account_fixed = account.replace('_', '-').lower()
    org_fixed = org.lower()
    base_url = f"https://{org_fixed}-{account_fixed}.snowflakecomputing.com"

    token = conn.rest.token

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": f"Snowflake Token=\"{token}\""
    }

    payload = {
        "messages": [
            {"role": "user", "content": [{"type": "text", "text": question}]}
        ]
    }

    url = f"{base_url}/api/v2/databases/{database}/schemas/{schema}/agents/{agent_name}:run"

    response = requests.post(url, headers=headers, json=payload, stream=True)

    if response.status_code != 200:
        cursor.close()
        conn.close()
        return {"error": f"HTTP {response.status_code}: {response.text[:500]}"}

    result = {
        "question": question,
        "answer": "",
        "tool_uses": [],
        "tool_results": []
    }

    current_event = None

    for line in response.iter_lines():
        if line:
            line_str = line.decode('utf-8')

            # Track event type
            if line_str.startswith('event: '):
                current_event = line_str[7:].strip()
                continue

            if line_str.startswith('data: '):
                data = line_str[6:]
                if data.strip() == '[DONE]':
                    break
                try:
                    parsed = json.loads(data)

                    # Capture tool uses (from response.tool_use events)
                    if current_event == 'response.tool_use' and parsed.get('name'):
                        result["tool_uses"].append({
                            "name": parsed.get('name'),
                            "type": parsed.get('type'),
                            "input": parsed.get('input'),
                            "tool_use_id": parsed.get('tool_use_id')
                        })

                    # Capture tool results
                    if current_event == 'response.tool_result' and 'content' in parsed:
                        for item in parsed['content']:
                            if isinstance(item, dict) and 'json' in item:
                                tool_result = item['json']
                                if 'sql' in tool_result:
                                    result["tool_results"].append({
                                        "sql": tool_result['sql'],
                                        "result_set": tool_result.get('result_set', {}).get('data', [])[:5]
                                    })
                                elif 'search_results' in tool_result:
                                    result["tool_results"].append({
                                        "search_results": tool_result['search_results'][:5]
                                    })
                                else:
                                    result["tool_results"].append(tool_result)

                    # Capture final text response (not thinking)
                    if current_event == 'response.text.delta' and 'text' in parsed:
                        result["answer"] += parsed.get('text', '')

                    # Also capture complete text block
                    if current_event == 'response.text' and 'text' in parsed:
                        # Use complete text if we haven't accumulated deltas
                        if not result["answer"]:
                            result["answer"] = parsed.get('text', '')

                except json.JSONDecodeError:
                    pass

    cursor.close()
    conn.close()
    return result


def main():
    if len(sys.argv) < 6:
        print(__doc__)
        print("\nError: Missing arguments")
        print(f"Got: {sys.argv[1:]}")
        sys.exit(1)

    database = sys.argv[1]
    schema = sys.argv[2]
    agent_name = sys.argv[3]
    question = sys.argv[4]
    connection = sys.argv[5]

    print(f"Invoking {database}.{schema}.{agent_name}...")
    print(f"Question: {question}\n")

    result = invoke_agent(database, schema, agent_name, question, connection)

    if "error" in result:
        print(f"ERROR: {result['error']}")
        sys.exit(1)

    print("=" * 60)
    print("TOOL USES:")
    print("=" * 60)
    for tu in result["tool_uses"]:
        print(f"  Tool: {tu['name']} ({tu['type']})")
        if tu['input']:
            print(f"  Input: {json.dumps(tu['input'], indent=4)}")
        print()

    print("=" * 60)
    print("TOOL RESULTS (SQL/Search):")
    print("=" * 60)
    for tr in result["tool_results"]:
        if 'sql' in tr:
            print(f"SQL:\n{tr['sql'][:500]}...")
            print(f"Results: {tr['result_set']}")
        elif 'search_results' in tr:
            print(f"Search results: {tr['search_results']}")
        else:
            print(json.dumps(tr, indent=2)[:500])
        print()

    print("=" * 60)
    print("FINAL ANSWER:")
    print("=" * 60)
    print(result["answer"].strip())


if __name__ == "__main__":
    main()
