# Testing Guide: Suggest New Feature

## Quick Start Testing

### Prerequisites
1. Ensure `GROQ_API_KEY` is set in your environment or `.env` file
2. Start the Flask application: `python app.py` or `start.bat`
3. Have at least one project created in the system

### Test Steps

#### Test 1: Basic Feature Generation
1. Navigate to any project detail page
2. Click on the **"💡 Suggest New Feature"** tab
3. Enter a project audit in the textarea:
   ```
   Project: E-commerce Platform
   Current Status:
   - Built with React and Node.js
   - Has user authentication and product catalog
   - Payment integration with Stripe
   - 1000+ registered users
   - Mobile responsiveness needs improvement
   - No admin dashboard yet
   ```
4. Click **"✨ Generate Feature Suggestions"**
5. **Expected Result**: 
   - Loading indicator appears
   - After 3-10 seconds, 5-8 suggestions are displayed
   - Each suggestion is numbered and clearly described
   - Timestamp is shown at the bottom

#### Test 2: Empty Input Validation
1. Clear the textarea completely
2. Click **"✨ Generate Feature Suggestions"**
3. **Expected Result**: 
   - Error message appears: "Please provide a project audit or current status."
   - Error disappears after 5 seconds
   - No API call is made

#### Test 3: Persistence
1. Generate suggestions for a project (follow Test 1)
2. Navigate away from the project
3. Return to the same project
4. Click on the **"💡 Suggest New Feature"** tab
5. **Expected Result**: 
   - Previous audit text is pre-filled in textarea
   - Previous suggestions are displayed
   - Timestamp shows when they were generated

#### Test 4: Regeneration
1. On a project with existing suggestions
2. Modify the audit text (add more details)
3. Click **"✨ Generate Feature Suggestions"** again
4. **Expected Result**: 
   - New suggestions are generated
   - Old suggestions are replaced
   - New timestamp is displayed
   - Updated audit text is saved

#### Test 5: Error Handling (API Failure)
1. Temporarily set invalid `GROQ_API_KEY` or disconnect internet
2. Try to generate suggestions
3. **Expected Result**: 
   - Error message is displayed
   - User-friendly error description
   - Button returns to normal state

#### Test 6: Multiple Projects
1. Generate suggestions for Project A
2. Navigate to Project B
3. Generate different suggestions for Project B
4. Return to Project A
5. **Expected Result**: 
   - Each project maintains its own suggestions
   - No cross-contamination of data

#### Test 7: Tab Navigation
1. Open a project
2. Click through all tabs: Questions → ClickUp → Weekly → Features
3. **Expected Result**: 
   - All tabs switch smoothly
   - Feature tab displays correctly
   - No console errors

#### Test 8: Long Audit Text
1. Enter a very long audit (500+ words)
2. Generate suggestions
3. **Expected Result**: 
   - Textarea handles long text with scrolling
   - API processes successfully
   - Suggestions are relevant to the detailed audit

## Database Verification

### Check Data Storage
```sql
-- Connect to projects.db
sqlite3 projects.db

-- View feature_suggestions table
SELECT * FROM feature_suggestions;

-- Check suggestions for specific project
SELECT * FROM feature_suggestions WHERE project_id = 'your-project-id';

-- Verify foreign key constraint
SELECT * FROM feature_suggestions fs
JOIN projects p ON fs.project_id = p.id;
```

## API Testing (Manual)

### Using curl
```bash
curl -X POST http://127.0.0.1:5000/generate-feature-suggestions \
  -H "Content-Type: application/json" \
  -d '{
    "project_id": "test-uuid-123",
    "project_name": "Test Project",
    "audit_text": "A simple web app with basic CRUD operations"
  }'
```

### Expected Response
```json
{
  "success": true,
  "suggestions": [
    "Add user authentication and authorization",
    "Implement search and filtering capabilities",
    "..."
  ],
  "suggestion_id": "generated-uuid"
}
```

## Browser Console Testing

### Check for JavaScript Errors
1. Open browser DevTools (F12)
2. Go to Console tab
3. Navigate to Feature Suggestions tab
4. Generate suggestions
5. **Expected Result**: No errors in console

### Verify Network Requests
1. Open DevTools → Network tab
2. Click "Generate Feature Suggestions"
3. **Expected Result**: 
   - POST request to `/generate-feature-suggestions`
   - Status: 200 OK
   - Response contains suggestions array

## Performance Testing

### Response Time
- **Target**: < 15 seconds for suggestion generation
- **Typical**: 3-10 seconds with Groq API
- **Measure**: Check Network tab timing

### Database Performance
```sql
-- Check query performance
EXPLAIN QUERY PLAN 
SELECT * FROM feature_suggestions WHERE project_id = 'test-id';

-- Should use index: idx_suggestions_project
```

## Edge Cases to Test

1. **Special Characters in Audit**
   - Test with emojis, quotes, newlines
   - Verify proper escaping

2. **Very Short Audit**
   - Enter just 1-2 words
   - Should still generate suggestions

3. **Concurrent Requests**
   - Open same project in two tabs
   - Generate suggestions in both
   - Verify no race conditions

4. **Browser Compatibility**
   - Test in Chrome, Firefox, Edge
   - Verify async/await support

## Common Issues & Solutions

### Issue: "Failed to generate feature suggestions"
**Cause**: Invalid or missing GROQ_API_KEY  
**Solution**: 
```bash
# Set environment variable
export GROQ_API_KEY="your-api-key-here"
# or add to .env file
echo "GROQ_API_KEY=your-api-key-here" >> .env
```

### Issue: Suggestions not persisting
**Cause**: Database write permissions  
**Solution**: 
```bash
chmod 666 projects.db
```

### Issue: Tab not appearing
**Cause**: Browser cache  
**Solution**: Hard refresh (Ctrl+Shift+R)

### Issue: Slow response
**Cause**: Groq API latency  
**Solution**: Normal behavior, wait for response

## Regression Testing Checklist

After implementing this feature, verify existing features still work:
- [ ] Project creation works
- [ ] Technical Questions tab displays correctly
- [ ] ClickUp Task Plan tab displays correctly
- [ ] Weekly Summary tab works
- [ ] Project deletion works
- [ ] Navigation between projects works
- [ ] All existing API endpoints respond correctly

## Success Criteria

✅ All 8 test cases pass  
✅ No console errors  
✅ Data persists correctly in database  
✅ API responds within acceptable time  
✅ UI is responsive and user-friendly  
✅ Error handling works properly  
✅ Existing features are not broken  

## Test Report Template

```
Test Date: ___________
Tester: ___________
Environment: Development / Production

Test Results:
[ ] Test 1: Basic Feature Generation - PASS / FAIL
[ ] Test 2: Empty Input Validation - PASS / FAIL
[ ] Test 3: Persistence - PASS / FAIL
[ ] Test 4: Regeneration - PASS / FAIL
[ ] Test 5: Error Handling - PASS / FAIL
[ ] Test 6: Multiple Projects - PASS / FAIL
[ ] Test 7: Tab Navigation - PASS / FAIL
[ ] Test 8: Long Audit Text - PASS / FAIL

Issues Found:
1. ___________
2. ___________

Notes:
___________
```

---

**Ready for Production**: After all tests pass and no critical issues are found.
